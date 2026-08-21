from pathlib import Path

import pytest

from nexus_science_agent import Document, EvidenceGraph, EvidenceRecord, ResearchInvariantError, SearchIndex


def _docs():
    return [
        Document("a", "demo://a", "DEMO", "2026-08-21T06:00:00Z", "content hash cache retransmit bytes"),
        Document("b", "demo://b", "DEMO", "2026-08-21T06:00:00Z", "latency depends on cpu congestion and round trip"),
    ]


def test_search_is_deterministic_and_content_addressed():
    docs = _docs()
    first = SearchIndex(docs)
    second = SearchIndex(docs)
    assert first.index_digest == second.index_digest
    assert first.search("cache bytes") == second.search("cache bytes")
    assert first.search("cache bytes")[0]["document_id"] == "a"


def test_document_content_change_changes_index_identity():
    docs = _docs()
    baseline = SearchIndex(docs).index_digest
    changed = [docs[0], Document("b", "demo://b", "DEMO", "2026-08-21T06:00:00Z", "different content")]
    assert SearchIndex(changed).index_digest != baseline


def test_evidence_graph_binds_to_exact_document_hash():
    docs = {doc.document_id: doc for doc in _docs()}
    graph = EvidenceGraph()
    graph.add_claim("C", "Warm cache may avoid retransmitting bytes")
    graph.add_evidence(EvidenceRecord("E", "C", "a", docs["a"].content_sha256, "SUPPORTS", 80, "fixture"), docs)
    summary = graph.summarize_claim("C")
    assert summary["status"] == "SUPPORTED_BY_CURRENT_EVIDENCE"
    assert summary["scientific_truth_authority"] == "NONE"
    with pytest.raises(ResearchInvariantError):
        graph.add_evidence(EvidenceRecord("E2", "C", "a", "00" * 32, "CONTRADICTS", 80, "fixture"), docs)


def test_mixed_evidence_is_not_collapsed_to_truth():
    docs = {doc.document_id: doc for doc in _docs()}
    graph = EvidenceGraph()
    graph.add_claim("C", "A disputed claim")
    graph.add_evidence(EvidenceRecord("E1", "C", "a", docs["a"].content_sha256, "SUPPORTS", 70, "fixture"), docs)
    graph.add_evidence(EvidenceRecord("E2", "C", "b", docs["b"].content_sha256, "CONTRADICTS", 60, "fixture"), docs)
    assert graph.summarize_claim("C")["status"] == "MIXED_EVIDENCE"


def test_demo_runner_exists():
    assert (Path(__file__).resolve().parents[1] / "tools/run_demo_research.py").is_file()
