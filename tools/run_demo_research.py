from __future__ import annotations

import json
from pathlib import Path

from nexus_science_agent import Document, EvidenceGraph, EvidenceRecord, SearchIndex

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    corpus = json.loads((ROOT / "fixtures/demo_corpus_v1.json").read_text(encoding="utf-8"))
    documents = [Document(**item) for item in corpus["documents"]]
    document_map = {doc.document_id: doc for doc in documents}
    index = SearchIndex(documents)

    query = "content dedup retransmit bytes latency"
    results = index.search(query, limit=10)

    graph = EvidenceGraph()
    graph.add_claim("C1", "A warm content-addressed cache can avoid retransmitting identical content bytes.")
    graph.add_claim("C2", "Content deduplication alone proves lower end-to-end latency for every workload.")
    graph.add_evidence(
        EvidenceRecord("E1", "C1", "dedup-principle", document_map["dedup-principle"].content_sha256, "SUPPORTS", 80, "whole fixture"),
        document_map,
    )
    graph.add_evidence(
        EvidenceRecord("E2", "C2", "latency-caveat", document_map["latency-caveat"].content_sha256, "CONTRADICTS", 90, "whole fixture"),
        document_map,
    )

    report = {
        "schema": "nexus.research-run/v1",
        "run_id": "demo-method-validation-001",
        "status": "DEMO_METHOD_VALIDATION_NOT_SCIENTIFIC_RESULT",
        "query": query,
        "index_digest": index.index_digest,
        "search_results": results,
        "evidence_graph": graph.artifact(),
        "claim_summaries": [graph.summarize_claim("C1"), graph.summarize_claim("C2")],
        "nexus_model_digest": None,
        "internet_retrieval": "NOT_PERFORMED",
        "scientific_truth_authority": "NONE",
    }
    out = ROOT / "research_output"
    out.mkdir(exist_ok=True)
    path = out / "demo_research_v1.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()
