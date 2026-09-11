from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Mapping, Optional, Protocol, Sequence, Tuple

from .contracts import (
    Claim,
    ClaimStatus,
    CompletenessCertificate,
    EvidenceItem,
    QueryIntent,
    ResearchQuestion,
    ResearchReport,
    ResearchRound,
    SearchHit,
    SearchQuery,
    SemanticObligation,
    SourceRecord,
)
from .evidence import EvidenceGraph, SourceRegistry, content_sha256, source_lineage
from .planner import ObligationPlanner, QueryPortfolioPlanner


class SearchProvider(Protocol):
    name: str
    def search(self, queries: Sequence[SearchQuery]) -> Sequence[SearchHit]: ...


class ContentFetcher(Protocol):
    def fetch(self, hit: SearchHit) -> Optional[SourceRecord]: ...


class ClaimExtractor(Protocol):
    def extract(
        self,
        question: ResearchQuestion,
        obligations: Sequence[SemanticObligation],
        source: SourceRecord,
    ) -> tuple[Sequence[Claim], Sequence[EvidenceItem]]: ...


class ReportSynthesizer(Protocol):
    def synthesize(
        self,
        question: ResearchQuestion,
        claims: Sequence[Claim],
        evidence: Sequence[EvidenceItem],
        sources: Sequence[SourceRecord],
        certificate: CompletenessCertificate,
    ) -> tuple[str, Sequence[str]]: ...


@dataclass(frozen=True)
class ResearchPolicy:
    max_rounds: int = 5
    max_queries_per_round: int = 10
    min_source_quality: float = 0.25
    min_independent_lineages: int = 2
    min_primary_source_coverage: float = 0.0
    require_contradiction_search: bool = True
    require_falsification: bool = True
    stop_if_eig_below: float = 0.04
    high_value_confidence: float = 0.25


class ResearchCortex:
    """R8.3 iterative web-research controller.

    Search providers are transport only. The controller owns query diversity,
    source deduplication, lineage discount, contradiction/falsification search,
    completeness and reproducibility metadata. A search result is never treated
    as evidence until content is fetched and a typed EvidenceItem is extracted.
    """

    def __init__(
        self,
        *,
        search_providers: Sequence[SearchProvider],
        fetcher: ContentFetcher,
        extractor: ClaimExtractor,
        synthesizer: ReportSynthesizer,
        policy: ResearchPolicy = ResearchPolicy(),
        obligation_planner: Optional[ObligationPlanner] = None,
        query_planner: Optional[QueryPortfolioPlanner] = None,
    ) -> None:
        if not search_providers:
            raise ValueError("at least one search provider is required")
        self.providers = list(search_providers)
        self.fetcher = fetcher
        self.extractor = extractor
        self.synthesizer = synthesizer
        self.policy = policy
        self.obligations = obligation_planner or ObligationPlanner()
        self.queries = query_planner or QueryPortfolioPlanner()

    @staticmethod
    def _refresh_obligations(
        obligations: Sequence[SemanticObligation],
        claims: Sequence[Claim],
    ) -> List[SemanticObligation]:
        covered: set[str] = set()
        for claim in claims:
            if claim.status in {ClaimStatus.SUPPORTED, ClaimStatus.REPRODUCED}:
                covered.update(claim.obligation_ids)
        return [replace(o, satisfied=o.obligation_id in covered) for o in obligations]

    @staticmethod
    def _has_contradiction_search(queries: Sequence[SearchQuery]) -> bool:
        return any(q.intent == QueryIntent.CONTRADICT for q in queries)

    @staticmethod
    def _has_falsification(evidence: Sequence[EvidenceItem]) -> bool:
        return any(e.relation.upper() in {"FALSIFIES", "FAILS_TO_REPLICATE", "CONTRADICTS"} for e in evidence)

    def _expected_information_gain(
        self,
        obligations: Sequence[SemanticObligation],
        claims: Sequence[Claim],
        sources: Sequence[SourceRecord],
    ) -> float:
        required = [o for o in obligations if o.required]
        unresolved = sum(1 for o in required if not o.satisfied)
        unresolved_frac = unresolved / max(1, len(required))
        uncertain_claims = sum(1 for c in claims if c.status in {ClaimStatus.OPEN, ClaimStatus.UNKNOWN, ClaimStatus.CONTRADICTED})
        uncertainty = uncertain_claims / max(1, len(claims)) if claims else 1.0
        lineages = len({s.lineage_id for s in sources})
        lineage_gap = max(0.0, (self.policy.min_independent_lineages - lineages) / max(1, self.policy.min_independent_lineages))
        return min(1.0, 0.55 * unresolved_frac + 0.30 * uncertainty + 0.15 * lineage_gap)

    def _certificate(
        self,
        question: ResearchQuestion,
        obligations: Sequence[SemanticObligation],
        claims: Sequence[Claim],
        evidence: Sequence[EvidenceItem],
        sources: Sequence[SourceRecord],
        all_queries: Sequence[SearchQuery],
    ) -> CompletenessCertificate:
        required = [o for o in obligations if o.required]
        coverage = sum(1 for o in required if o.satisfied) / max(1, len(required))
        primary_ids = {s.source_id for s in sources if s.is_primary}
        supported_claims = [c for c in claims if c.status in {ClaimStatus.SUPPORTED, ClaimStatus.REPRODUCED}]
        primary_backed = {
            e.claim_id for e in evidence
            if e.source_id in primary_ids and e.relation.upper() in {"SUPPORTS", "REPLICATES"}
        }
        primary_coverage = len({c.claim_id for c in supported_claims if c.claim_id in primary_backed}) / max(1, len(supported_claims))
        high_value_unresolved = sum(
            1 for c in claims
            if c.confidence >= self.policy.high_value_confidence and c.status in {ClaimStatus.UNKNOWN, ClaimStatus.CONTRADICTED, ClaimStatus.OPEN}
        )
        freshness_ok = True
        if question.freshness_days is not None:
            # Strictly require publication metadata for a fresh question. Date
            # comparison itself is delegated to provider/fetcher normalization.
            freshness_ok = bool(sources) and all(s.published_at for s in sources if s.quality_score >= self.policy.min_source_quality)
        cited_sources = {e.source_id for e in evidence}
        traceability = len(cited_sources & {s.source_id for s in sources}) / max(1, len(cited_sources)) if cited_sources else 0.0
        return CompletenessCertificate(
            obligation_coverage=coverage,
            primary_source_coverage=primary_coverage,
            contradiction_search_done=self._has_contradiction_search(all_queries),
            falsification_attempted=self._has_falsification(evidence),
            independent_lineages=len({s.lineage_id for s in sources}),
            unresolved_high_value_claims=high_value_unresolved,
            freshness_satisfied=freshness_ok,
            citation_traceability=traceability,
        )

    def run(self, question: ResearchQuestion) -> ResearchReport:
        obligations = self.obligations.decompose(question)
        registry = SourceRegistry()
        graph = EvidenceGraph()
        all_queries: List[SearchQuery] = []
        rounds: List[ResearchRound] = []
        query_batch = self.queries.initial_queries(question, obligations)

        for round_index in range(self.policy.max_rounds):
            query_batch = sorted(query_batch, key=lambda q: (-q.priority, q.query_id))[: self.policy.max_queries_per_round]
            all_queries.extend(query_batch)
            hits: List[SearchHit] = []
            for provider in self.providers:
                hits.extend(provider.search(query_batch))

            new_source_ids: List[str] = []
            new_claim_ids: List[str] = []
            seen_hit_keys: set[tuple[str, str]] = set()
            for hit in hits:
                key = (hit.url, hit.title)
                if key in seen_hit_keys:
                    continue
                seen_hit_keys.add(key)
                source = self.fetcher.fetch(hit)
                if source is None or source.quality_score < self.policy.min_source_quality:
                    continue
                if not source.content_sha256:
                    source = replace(source, content_sha256=content_sha256(source.text))
                if not source.lineage_id:
                    source = replace(source, lineage_id=source_lineage(source.url))
                source_id, is_new = registry.add(source)
                if not is_new:
                    continue
                new_source_ids.append(source_id)
                claims, evidence = self.extractor.extract(question, obligations, registry.get(source_id))
                for claim in claims:
                    graph.add_claim(claim)
                    new_claim_ids.append(claim.claim_id)
                for row in evidence:
                    graph.add_evidence(row)

            rescored = graph.rescored_claims(registry.values())
            for claim in rescored:
                graph.claims[claim.claim_id] = claim
            obligations = self._refresh_obligations(obligations, rescored)
            unresolved = [o for o in obligations if o.required and not o.satisfied]
            eig = self._expected_information_gain(obligations, rescored, registry.values())
            cert = self._certificate(question, obligations, rescored, list(graph.evidence.values()), registry.values(), all_queries)

            stop_reason = ""
            if cert.eligible_to_finalize and cert.primary_source_coverage >= self.policy.min_primary_source_coverage:
                stop_reason = "complete"
            elif eig < self.policy.stop_if_eig_below:
                stop_reason = "low_expected_information_gain"
            elif round_index + 1 >= self.policy.max_rounds:
                stop_reason = "round_budget_exhausted"

            rounds.append(
                ResearchRound(
                    index=round_index,
                    queries=list(query_batch),
                    source_ids=new_source_ids,
                    new_claim_ids=new_claim_ids,
                    unresolved_obligations=[o.obligation_id for o in unresolved],
                    expected_information_gain=eig,
                    stop_reason=stop_reason,
                )
            )
            if stop_reason:
                break

            leading = [c.text for c in rescored if c.status in {ClaimStatus.SUPPORTED, ClaimStatus.REPRODUCED, ClaimStatus.CONTRADICTED}]
            query_batch = self.queries.followup_queries(question, unresolved, leading)
            if not query_batch:
                rounds[-1].stop_reason = "no_followup_queries"
                break

        final_claims = graph.rescored_claims(registry.values())
        obligations = self._refresh_obligations(obligations, final_claims)
        final_cert = self._certificate(question, obligations, final_claims, list(graph.evidence.values()), registry.values(), all_queries)
        summary, open_questions = self.synthesizer.synthesize(
            question,
            final_claims,
            list(graph.evidence.values()),
            registry.values(),
            final_cert,
        )
        return ResearchReport(
            question=question,
            claims=final_claims,
            evidence=list(graph.evidence.values()),
            sources=registry.values(),
            rounds=rounds,
            certificate=final_cert,
            summary=summary,
            open_questions=list(open_questions),
            search_queries=all_queries,
            source_manifest={s.source_id: s.content_sha256 for s in registry.values()},
        )
