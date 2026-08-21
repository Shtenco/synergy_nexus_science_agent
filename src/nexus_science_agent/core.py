from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Iterable


class ResearchInvariantError(ValueError):
    pass


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _utc(value: str) -> None:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ResearchInvariantError("timestamp must be RFC3339 UTC Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ResearchInvariantError("invalid timestamp") from exc
    if parsed.tzinfo != timezone.utc:
        raise ResearchInvariantError("timestamp must be UTC")


def _tokens(text: str) -> list[str]:
    return re.findall(r"[0-9A-Za-zА-Яа-яЁё_\-]+", text.lower())


@dataclass(frozen=True)
class Document:
    document_id: str
    uri: str
    source_kind: str
    retrieved_at: str
    content: str

    def __post_init__(self) -> None:
        if not self.document_id or not self.uri or not self.source_kind:
            raise ResearchInvariantError("document identity fields are required")
        _utc(self.retrieved_at)
        if not isinstance(self.content, str) or not self.content:
            raise ResearchInvariantError("document content is required")

    @property
    def content_sha256(self) -> str:
        return _sha(self.content.encode("utf-8"))

    def identity(self) -> dict[str, str]:
        return {
            "document_id": self.document_id,
            "uri": self.uri,
            "source_kind": self.source_kind,
            "retrieved_at": self.retrieved_at,
            "content_sha256": self.content_sha256,
        }


class SearchIndex:
    """Small deterministic local search engine for reproducible research inputs.

    V1 intentionally uses an integer ranking formula rather than floating-point BM25.
    It is a provenance/search substrate, not a claim of web-search SOTA.
    """

    def __init__(self, documents: Iterable[Document]):
        docs = list(documents)
        if not docs:
            raise ResearchInvariantError("index requires at least one document")
        ids = [doc.document_id for doc in docs]
        if len(ids) != len(set(ids)):
            raise ResearchInvariantError("document ids must be unique")
        self._docs = {doc.document_id: doc for doc in docs}
        self._term_counts = {doc.document_id: Counter(_tokens(doc.content)) for doc in docs}
        doc_freq: dict[str, int] = defaultdict(int)
        for counts in self._term_counts.values():
            for token in counts:
                doc_freq[token] += 1
        self._doc_freq = dict(doc_freq)
        identities = [self._docs[doc_id].identity() for doc_id in sorted(self._docs)]
        self.index_digest = _sha(_canonical({"schema": "nexus.search-index/v1", "documents": identities}))

    def search(self, query: str, *, limit: int = 10) -> list[dict[str, object]]:
        if not isinstance(query, str) or not query.strip():
            raise ResearchInvariantError("query is required")
        if isinstance(limit, bool) or not isinstance(limit, int) or not (1 <= limit <= 100):
            raise ResearchInvariantError("limit must be a safe positive integer <=100")
        query_counts = Counter(_tokens(query))
        if not query_counts:
            return []
        total_docs = len(self._docs)
        scored: list[tuple[int, str]] = []
        for doc_id, counts in self._term_counts.items():
            score = 0
            for token, query_tf in query_counts.items():
                tf = counts.get(token, 0)
                if tf:
                    df = self._doc_freq[token]
                    # Deterministic integer rarity weighting; larger when df is small.
                    rarity = 1_000_000 * total_docs // df
                    score += tf * query_tf * rarity
            if score > 0:
                scored.append((score, doc_id))
        scored.sort(key=lambda item: (-item[0], item[1]))
        result = []
        for score, doc_id in scored[:limit]:
            doc = self._docs[doc_id]
            result.append({
                "document_id": doc_id,
                "score_units": score,
                "content_sha256": doc.content_sha256,
                "uri": doc.uri,
            })
        return result


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    claim_id: str
    document_id: str
    document_content_sha256: str
    relation: str
    quality_score: int
    locator: str

    def __post_init__(self) -> None:
        if self.relation not in {"SUPPORTS", "CONTRADICTS"}:
            raise ResearchInvariantError("unknown evidence relation")
        if isinstance(self.quality_score, bool) or not isinstance(self.quality_score, int) or not (0 <= self.quality_score <= 100):
            raise ResearchInvariantError("quality_score must be integer 0..100")
        for value in (self.evidence_id, self.claim_id, self.document_id, self.locator):
            if not isinstance(value, str) or not value:
                raise ResearchInvariantError("evidence identity fields are required")
        if len(self.document_content_sha256) != 64:
            raise ResearchInvariantError("document hash must be SHA-256 hex")
        try:
            int(self.document_content_sha256, 16)
        except ValueError as exc:
            raise ResearchInvariantError("document hash must be SHA-256 hex") from exc


class EvidenceGraph:
    def __init__(self) -> None:
        self._claims: dict[str, str] = {}
        self._evidence: dict[str, EvidenceRecord] = {}

    def add_claim(self, claim_id: str, statement: str) -> None:
        if not claim_id or not statement:
            raise ResearchInvariantError("claim id and statement are required")
        if claim_id in self._claims:
            raise ResearchInvariantError("claim id already exists")
        self._claims[claim_id] = statement

    def add_evidence(self, record: EvidenceRecord, documents: dict[str, Document]) -> None:
        if record.evidence_id in self._evidence:
            raise ResearchInvariantError("evidence id already exists")
        if record.claim_id not in self._claims:
            raise ResearchInvariantError("evidence references unknown claim")
        if record.document_id not in documents:
            raise ResearchInvariantError("evidence references unknown document")
        if documents[record.document_id].content_sha256 != record.document_content_sha256:
            raise ResearchInvariantError("evidence document hash mismatch")
        self._evidence[record.evidence_id] = record

    def summarize_claim(self, claim_id: str) -> dict[str, object]:
        if claim_id not in self._claims:
            raise ResearchInvariantError("unknown claim")
        relevant = [record for record in self._evidence.values() if record.claim_id == claim_id]
        support = sum(record.quality_score for record in relevant if record.relation == "SUPPORTS")
        contradict = sum(record.quality_score for record in relevant if record.relation == "CONTRADICTS")
        if support == 0 and contradict == 0:
            status = "INSUFFICIENT_EVIDENCE"
        elif support > 0 and contradict == 0:
            status = "SUPPORTED_BY_CURRENT_EVIDENCE"
        elif contradict > 0 and support == 0:
            status = "CONTRADICTED_BY_CURRENT_EVIDENCE"
        else:
            status = "MIXED_EVIDENCE"
        payload = {
            "claim_id": claim_id,
            "statement": self._claims[claim_id],
            "support_score": support,
            "contradiction_score": contradict,
            "status": status,
            "scientific_truth_authority": "NONE",
            "evidence_ids": sorted(record.evidence_id for record in relevant),
        }
        return payload

    def artifact(self) -> dict[str, object]:
        payload = {
            "schema": "nexus.evidence-graph/v1",
            "claims": [{"claim_id": key, "statement": self._claims[key]} for key in sorted(self._claims)],
            "evidence": [self._evidence[key].__dict__ for key in sorted(self._evidence)],
            "scientific_truth_authority": "NONE",
        }
        return payload | {"digest": _sha(_canonical(payload))}
