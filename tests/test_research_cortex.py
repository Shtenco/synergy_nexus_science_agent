from __future__ import annotations

import hashlib
import unittest

from nexus_research.contracts import (
    Claim,
    ClaimStatus,
    EvidenceItem,
    QueryIntent,
    ResearchQuestion,
    SearchHit,
    SourceRecord,
)
from nexus_research.engine import ResearchCortex, ResearchPolicy


class MockSearch:
    name = "mock-search"

    def search(self, queries):
        out = []
        for q in queries:
            if q.intent == QueryIntent.CONTRADICT:
                out.append(SearchHit(q.query_id, "https://critic.example.org/paper", "Contradicting replication"))
            elif q.intent == QueryIntent.PRIMARY:
                out.append(SearchHit(q.query_id, "https://primary.example.edu/study", "Primary study"))
            else:
                out.append(SearchHit(q.query_id, "https://mirror.example.net/copy", "Secondary summary"))
        return out


class MockFetcher:
    def fetch(self, hit):
        if "critic" in hit.url:
            text = "Independent replication finds the claimed effect absent under stricter controls."
            lineage = "critic-lab"
            primary = True
            quality = 0.95
        elif "primary" in hit.url:
            text = "Primary experiment reports a positive effect with method and sample."
            lineage = "primary-lab"
            primary = True
            quality = 1.0
        else:
            text = "A secondary article repeats that the effect is positive."
            lineage = "primary-lab"  # correlated with the primary lineage on purpose
            primary = False
            quality = 0.50
        return SourceRecord(
            source_id=hashlib.blake2s(hit.url.encode(), digest_size=6).hexdigest(),
            url=hit.url,
            title=hit.title,
            text=text,
            content_sha256=hashlib.sha256(text.encode()).hexdigest(),
            retrieved_at="2026-09-11T00:00:00Z",
            published_at="2026-09-01",
            lineage_id=lineage,
            is_primary=primary,
            quality_score=quality,
        )


class MockExtractor:
    def extract(self, question, obligations, source):
        oid = tuple(o.obligation_id for o in obligations)
        claim = Claim("effect", "The intervention has a positive effect", oid, ClaimStatus.OPEN, 0.5)
        if "critic" in source.url:
            evidence = EvidenceItem("e-critic", "effect", source.source_id, "CONTRADICTS", confidence=0.95)
        elif "primary" in source.url:
            evidence = EvidenceItem("e-primary", "effect", source.source_id, "SUPPORTS", confidence=0.90)
        else:
            evidence = EvidenceItem("e-copy", "effect", source.source_id, "SUPPORTS", confidence=0.80)
        return [claim], [evidence]


class MockSynthesizer:
    def synthesize(self, question, claims, evidence, sources, certificate):
        status = claims[0].status.value if claims else "NONE"
        return f"status={status}; complete={certificate.eligible_to_finalize}", []


class ResearchCortexContracts(unittest.TestCase):
    def make(self):
        return ResearchCortex(
            search_providers=[MockSearch()],
            fetcher=MockFetcher(),
            extractor=MockExtractor(),
            synthesizer=MockSynthesizer(),
            policy=ResearchPolicy(max_rounds=2, min_primary_source_coverage=0.0),
        )

    def test_initial_portfolio_always_contains_contradiction_search(self):
        cortex = self.make()
        report = cortex.run(ResearchQuestion("Does intervention X work?"))
        self.assertTrue(any(q.intent == QueryIntent.CONTRADICT for q in report.search_queries))
        self.assertTrue(report.certificate.contradiction_search_done)

    def test_search_hit_is_not_evidence_until_fetched_and_extracted(self):
        report = self.make().run(ResearchQuestion("Does intervention X work?"))
        self.assertGreaterEqual(len(report.sources), 2)
        self.assertGreaterEqual(len(report.evidence), 2)
        self.assertTrue(all(e.source_id in report.source_manifest for e in report.evidence))

    def test_correlated_copy_does_not_become_independent_third_witness(self):
        report = self.make().run(ResearchQuestion("Does intervention X work?"))
        lineages = {s.lineage_id for s in report.sources}
        self.assertEqual(lineages, {"primary-lab", "critic-lab"})
        self.assertEqual(report.certificate.independent_lineages, 2)

    def test_contradictory_high_quality_sources_prevent_fake_certainty(self):
        report = self.make().run(ResearchQuestion("Does intervention X work?"))
        effect = next(c for c in report.claims if c.claim_id == "effect")
        self.assertLess(effect.confidence, 0.50)
        self.assertIn(effect.status, {ClaimStatus.SUPPORTED, ClaimStatus.CONTRADICTED, ClaimStatus.UNKNOWN})

    def test_reproducibility_manifest_contains_content_hashes(self):
        report = self.make().run(ResearchQuestion("Does intervention X work?"))
        self.assertEqual(len(report.source_manifest), len(report.sources))
        self.assertTrue(all(len(v) == 64 for v in report.source_manifest.values()))


if __name__ == "__main__":
    unittest.main()
