from __future__ import annotations

import copy

import pytest

from nexus_science_agent.core import Document, EvidenceGraph, EvidenceRecord
from nexus_science_agent.service_v4 import ScienceServiceError, ScienceServiceV4, decode_request_line, encode_response_line, verify_response


def service():
    docs = [
        Document("doc-a", "local://a", "LOCAL_FIXTURE", "2026-08-21T16:00:00Z", "graph evidence supports deterministic research"),
        Document("doc-b", "local://b", "LOCAL_FIXTURE", "2026-08-21T16:00:00Z", "contradictory evidence must remain visible"),
    ]
    graph = EvidenceGraph()
    graph.add_claim("claim-1", "Deterministic evidence graphs preserve provenance")
    graph.add_evidence(EvidenceRecord("ev-1", "claim-1", "doc-a", docs[0].content_sha256, "SUPPORTS", 80, "local:a"), {d.document_id:d for d in docs})
    graph.add_evidence(EvidenceRecord("ev-2", "claim-1", "doc-b", docs[1].content_sha256, "CONTRADICTS", 30, "local:b"), {d.document_id:d for d in docs})
    return ScienceServiceV4(docs, graph)


def test_search_local_is_read_only_and_digest_bound():
    svc = service()
    request = {"schema":"nexus.science-service-request/v1","request_id":"r1","operation":"SEARCH_LOCAL","corpus_digest":svc.corpus_digest,"query":"deterministic graph","limit":10}
    response = svc.handle(request)
    verify_response(response)
    assert response["status"] == "OK"
    assert response["scientific_truth_authority"] == "NONE"
    assert response["execution_authority"] == "NONE"
    assert response["result"]["hits"]


def test_claim_summary_preserves_mixed_evidence():
    svc = service()
    request = {"schema":"nexus.science-service-request/v1","request_id":"r2","operation":"CLAIM_SUMMARY","corpus_digest":svc.corpus_digest,"evidence_graph_digest":svc.evidence_graph_digest,"claim_id":"claim-1"}
    response = svc.handle(request)
    verify_response(response)
    assert response["result"]["status"] == "MIXED_EVIDENCE"
    assert response["result"]["scientific_truth_authority"] == "NONE"


def test_remote_url_fetch_cannot_be_injected_into_service_request():
    svc = service()
    request = {"schema":"nexus.science-service-request/v1","request_id":"r3","operation":"SEARCH_LOCAL","corpus_digest":svc.corpus_digest,"query":"x","limit":1,"url":"http://127.0.0.1/admin"}
    with pytest.raises(ScienceServiceError):
        svc.handle(request)


def test_stale_corpus_digest_fails_closed():
    svc = service()
    request = {"schema":"nexus.science-service-request/v1","request_id":"r4","operation":"SEARCH_LOCAL","corpus_digest":"00"*32,"query":"graph","limit":1}
    with pytest.raises(ScienceServiceError):
        svc.handle(request)


def test_fresh_hash_cannot_grant_authority():
    svc = service()
    request = {"schema":"nexus.science-service-request/v1","request_id":"r5","operation":"SEARCH_LOCAL","corpus_digest":svc.corpus_digest,"query":"graph","limit":1}
    response = svc.handle(request)
    tampered = copy.deepcopy(response)
    tampered["execution_authority"] = "RUN"
    with pytest.raises(ScienceServiceError):
        verify_response(tampered)


def test_jsonl_framing_is_bounded():
    raw = b'{"schema":"nexus.science-service-request/v1"}\n'
    assert decode_request_line(raw)["schema"] == "nexus.science-service-request/v1"
    assert encode_response_line({"status":"OK"}).endswith(b"\n")
    with pytest.raises(ScienceServiceError):
        decode_request_line(b"{}\n{}\n")
