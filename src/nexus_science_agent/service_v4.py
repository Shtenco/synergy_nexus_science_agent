from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

from .core import Document, EvidenceGraph, ResearchInvariantError, SearchIndex


class ScienceServiceError(ValueError):
    pass


def _canonical(value: Any) -> bytes:
    def check(v: Any) -> None:
        if v is None or isinstance(v, (str, bool)):
            return
        if isinstance(v, int) and not isinstance(v, bool):
            if abs(v) > 2**53 - 1:
                raise ScienceServiceError("unsafe integer")
            return
        if isinstance(v, float):
            raise ScienceServiceError("floats are forbidden in service bytes")
        if isinstance(v, list):
            for item in v:
                check(item)
            return
        if isinstance(v, dict):
            if any(not isinstance(k, str) for k in v):
                raise ScienceServiceError("object keys must be strings")
            for item in v.values():
                check(item)
            return
        raise ScienceServiceError(f"unsupported value: {type(v)!r}")
    check(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def decode_request_line(raw: bytes, *, max_bytes: int = 16_384) -> dict[str, Any]:
    if not isinstance(raw, (bytes, bytearray)) or not raw or len(raw) > max_bytes:
        raise ScienceServiceError("request frame size invalid")
    if b"\n" in raw.rstrip(b"\n"):
        raise ScienceServiceError("exactly one JSON line is allowed")
    try:
        value = json.loads(bytes(raw).decode("utf-8"))
    except Exception as exc:
        raise ScienceServiceError("invalid UTF-8 JSON request") from exc
    if not isinstance(value, dict):
        raise ScienceServiceError("request must be an object")
    _canonical(value)
    return value


def encode_response_line(payload: dict[str, Any], *, max_bytes: int = 262_144) -> bytes:
    raw = _canonical(payload) + b"\n"
    if len(raw) > max_bytes:
        raise ScienceServiceError("response frame too large")
    return raw


class ScienceServiceV4:
    """Bounded read-only service over a locally provisioned research corpus.

    Network retrieval and evidence ingestion are deliberately out of band.
    Remote requests can only query existing SearchIndex/EvidenceGraph state.
    """

    def __init__(self, documents: Iterable[Document], evidence_graph: EvidenceGraph):
        docs = list(documents)
        if not docs:
            raise ScienceServiceError("service requires a local corpus")
        self._documents = {doc.document_id: doc for doc in docs}
        if len(self._documents) != len(docs):
            raise ScienceServiceError("document ids must be unique")
        self._index = SearchIndex(docs)
        self._graph = evidence_graph
        graph_artifact = self._graph.artifact()
        self.corpus_digest = self._index.index_digest
        self.evidence_graph_digest = graph_artifact["digest"]

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(request, dict):
            raise ScienceServiceError("request must be an object")
        operation = request.get("operation")
        if operation == "SEARCH_LOCAL":
            return self._search(request)
        if operation == "CLAIM_SUMMARY":
            return self._claim_summary(request)
        raise ScienceServiceError("operation is not allowlisted")

    def _base(self, request: dict[str, Any], expected: set[str]) -> tuple[str, str]:
        if set(request) != expected:
            raise ScienceServiceError("unexpected request shape")
        if request["schema"] != "nexus.science-service-request/v1":
            raise ScienceServiceError("unexpected request schema")
        request_id = request["request_id"]
        if not isinstance(request_id, str) or not (1 <= len(request_id) <= 128):
            raise ScienceServiceError("request_id length invalid")
        corpus_digest = request["corpus_digest"]
        if corpus_digest != self.corpus_digest:
            raise ScienceServiceError("request corpus digest is stale or foreign")
        return request_id, _sha(request)

    def _search(self, request: dict[str, Any]) -> dict[str, Any]:
        request_id, request_digest = self._base(
            request,
            {"schema", "request_id", "operation", "corpus_digest", "query", "limit"},
        )
        if request["operation"] != "SEARCH_LOCAL":
            raise ScienceServiceError("operation mismatch")
        query = request["query"]
        if not isinstance(query, str) or not query.strip() or len(query) > 4096:
            raise ScienceServiceError("query length invalid")
        limit = request["limit"]
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 20:
            raise ScienceServiceError("limit must be integer 1..20")
        hits = self._index.search(query, limit=limit)
        body = {
            "schema": "nexus.science-service-response/v1",
            "request_id": request_id,
            "operation": "SEARCH_LOCAL",
            "status": "OK",
            "request_digest": request_digest,
            "corpus_digest": self.corpus_digest,
            "result": {"hits": hits},
            "scientific_truth_authority": "NONE",
            "execution_authority": "NONE",
        }
        return body | {"response_digest": _sha(body)}

    def _claim_summary(self, request: dict[str, Any]) -> dict[str, Any]:
        request_id, request_digest = self._base(
            request,
            {"schema", "request_id", "operation", "corpus_digest", "evidence_graph_digest", "claim_id"},
        )
        if request["operation"] != "CLAIM_SUMMARY":
            raise ScienceServiceError("operation mismatch")
        if request["evidence_graph_digest"] != self.evidence_graph_digest:
            raise ScienceServiceError("evidence graph digest is stale or foreign")
        claim_id = request["claim_id"]
        if not isinstance(claim_id, str) or not (1 <= len(claim_id) <= 256):
            raise ScienceServiceError("claim_id length invalid")
        try:
            summary = self._graph.summarize_claim(claim_id)
        except ResearchInvariantError as exc:
            raise ScienceServiceError(str(exc)) from exc
        body = {
            "schema": "nexus.science-service-response/v1",
            "request_id": request_id,
            "operation": "CLAIM_SUMMARY",
            "status": "OK",
            "request_digest": request_digest,
            "corpus_digest": self.corpus_digest,
            "evidence_graph_digest": self.evidence_graph_digest,
            "result": summary,
            "scientific_truth_authority": "NONE",
            "execution_authority": "NONE",
        }
        return body | {"response_digest": _sha(body)}


def verify_response(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict) or "response_digest" not in payload:
        raise ScienceServiceError("response digest is required")
    if payload.get("scientific_truth_authority") != "NONE" or payload.get("execution_authority") != "NONE":
        raise ScienceServiceError("service response cannot grant authority")
    body = dict(payload)
    digest = body.pop("response_digest")
    if digest != _sha(body):
        raise ScienceServiceError("response digest mismatch")
