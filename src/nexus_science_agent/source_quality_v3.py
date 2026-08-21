from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any
from urllib.parse import urlparse


class SourceQualityError(ValueError):
    pass


_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_DOI = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)
_ARXIV = re.compile(r"^(?:arxiv:)?(\d{4}\.\d{4,5})(?:v\d+)?$", re.IGNORECASE)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _digest(value: str, label: str) -> str:
    if not isinstance(value, str) or not _HEX64.fullmatch(value):
        raise SourceQualityError(f"{label} must be lowercase SHA-256")
    return value


def canonicalize_doi(value: str) -> str:
    if not isinstance(value, str):
        raise SourceQualityError("DOI must be string")
    text = value.strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if text.lower().startswith(prefix):
            text = text[len(prefix):]
            break
    text = text.lower()
    if not _DOI.fullmatch(text):
        raise SourceQualityError("invalid DOI")
    return f"https://doi.org/{text}"


def canonicalize_arxiv(value: str) -> str:
    if not isinstance(value, str):
        raise SourceQualityError("arXiv id must be string")
    text = value.strip()
    if text.startswith("https://arxiv.org/abs/"):
        text = text.split("/abs/", 1)[1]
    match = _ARXIV.fullmatch(text)
    if not match:
        raise SourceQualityError("invalid modern arXiv id")
    return f"https://arxiv.org/abs/{match.group(1)}"


def canonicalize_repository(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise SourceQualityError("repository URL required")
    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.hostname not in {"github.com", "gitlab.com"}:
        raise SourceQualityError("v3 repository identity supports canonical HTTPS GitHub/GitLab only")
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        raise SourceQualityError("repository URL must include owner/project")
    return f"https://{parsed.hostname}/{parts[0]}/{parts[1]}"


@dataclass(frozen=True)
class SourceAssessment:
    source_id: str
    source_kind: str
    canonical_locator: str
    document_content_sha256: str
    metadata_evidence_digest: str
    primary_source: bool
    peer_review_status: str
    retraction_status: str
    code_available: bool
    data_available: bool

    def __post_init__(self) -> None:
        if not self.source_id:
            raise SourceQualityError("source_id required")
        if self.source_kind not in {"DOI_ARTICLE", "ARXIV_PREPRINT", "CODE_REPOSITORY", "DATASET", "WEB_DOCUMENT"}:
            raise SourceQualityError("unknown source_kind")
        _digest(self.document_content_sha256, "document_content_sha256")
        _digest(self.metadata_evidence_digest, "metadata_evidence_digest")
        if self.peer_review_status not in {"PEER_REVIEWED", "PREPRINT", "NOT_APPLICABLE", "UNKNOWN"}:
            raise SourceQualityError("unknown peer_review_status")
        if self.retraction_status not in {"NOT_RETRACTED_AT_CHECK", "RETRACTED", "UNKNOWN"}:
            raise SourceQualityError("unknown retraction_status")
        if not all(isinstance(v, bool) for v in (self.primary_source, self.code_available, self.data_available)):
            raise SourceQualityError("source flags must be booleans")
        expected_locator = {
            "DOI_ARTICLE": canonicalize_doi,
            "ARXIV_PREPRINT": canonicalize_arxiv,
            "CODE_REPOSITORY": canonicalize_repository,
        }.get(self.source_kind)
        if expected_locator is not None and expected_locator(self.canonical_locator) != self.canonical_locator:
            raise SourceQualityError("canonical locator mismatch")
        if self.source_kind in {"WEB_DOCUMENT", "DATASET"}:
            parsed = urlparse(self.canonical_locator)
            if parsed.scheme != "https" or not parsed.hostname:
                raise SourceQualityError("web/dataset locator must be canonical HTTPS URL")

    @property
    def gate_status(self) -> str:
        if self.retraction_status == "RETRACTED":
            return "BLOCKED_RETRACTED"
        if self.retraction_status == "UNKNOWN" or self.peer_review_status == "UNKNOWN":
            return "UNKNOWN_METADATA"
        if self.primary_source and self.peer_review_status == "PEER_REVIEWED" and self.retraction_status == "NOT_RETRACTED_AT_CHECK":
            return "HIGH_CONFIDENCE_ELIGIBLE"
        return "ELIGIBLE_WITH_CAVEATS"

    def artifact(self) -> dict[str, Any]:
        body = {
            "schema": "nexus.source-assessment/v3",
            "source_id": self.source_id,
            "source_kind": self.source_kind,
            "canonical_locator": self.canonical_locator,
            "document_content_sha256": self.document_content_sha256,
            "metadata_evidence_digest": self.metadata_evidence_digest,
            "primary_source": self.primary_source,
            "peer_review_status": self.peer_review_status,
            "retraction_status": self.retraction_status,
            "code_available": self.code_available,
            "data_available": self.data_available,
            "gate_status": self.gate_status,
            "scientific_truth_authority": "NONE",
            "automatic_evidence_score_authority": "NONE"
        }
        return body | {"digest": _sha(body)}


def verify_source_assessment(payload: dict[str, Any]) -> dict[str, Any]:
    expected = {
        "schema", "source_id", "source_kind", "canonical_locator", "document_content_sha256",
        "metadata_evidence_digest", "primary_source", "peer_review_status", "retraction_status",
        "code_available", "data_available", "gate_status", "scientific_truth_authority",
        "automatic_evidence_score_authority", "digest"
    }
    if set(payload) != expected or payload["schema"] != "nexus.source-assessment/v3":
        raise SourceQualityError("unexpected source-assessment shape/schema")
    assessment = SourceAssessment(
        source_id=payload["source_id"], source_kind=payload["source_kind"],
        canonical_locator=payload["canonical_locator"], document_content_sha256=payload["document_content_sha256"],
        metadata_evidence_digest=payload["metadata_evidence_digest"], primary_source=payload["primary_source"],
        peer_review_status=payload["peer_review_status"], retraction_status=payload["retraction_status"],
        code_available=payload["code_available"], data_available=payload["data_available"],
    )
    rebuilt = assessment.artifact()
    if rebuilt != payload:
        raise SourceQualityError("source assessment does not match deterministic classification")
    return payload
