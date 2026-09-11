from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple

from .contracts import ResearchReport


@dataclass(frozen=True)
class CandidateScore:
    total: float
    obligation_coverage: float
    citation_traceability: float
    lineage_score: float
    contradiction_score: float
    falsification_score: float
    unresolved_penalty: float
    source_quality_score: float


def score_report(report: ResearchReport) -> CandidateScore:
    cert = report.certificate
    quality = (
        sum(max(0.0, min(1.0, s.quality_score)) for s in report.sources) / max(1, len(report.sources))
    )
    lineage_score = min(1.0, cert.independent_lineages / 4.0)
    contradiction = 1.0 if cert.contradiction_search_done else 0.0
    falsification = 1.0 if cert.falsification_attempted else 0.0
    unresolved_penalty = min(1.0, cert.unresolved_high_value_claims / max(1, len(report.claims)))
    total = (
        0.28 * cert.obligation_coverage
        + 0.18 * cert.citation_traceability
        + 0.14 * lineage_score
        + 0.12 * contradiction
        + 0.12 * falsification
        + 0.16 * quality
        - 0.30 * unresolved_penalty
    )
    return CandidateScore(
        total=total,
        obligation_coverage=cert.obligation_coverage,
        citation_traceability=cert.citation_traceability,
        lineage_score=lineage_score,
        contradiction_score=contradiction,
        falsification_score=falsification,
        unresolved_penalty=unresolved_penalty,
        source_quality_score=quality,
    )


class EvidenceBestOfN:
    """Select research trajectories by evidence quality, never model confidence."""

    def choose(self, reports: Sequence[ResearchReport]) -> tuple[ResearchReport, CandidateScore]:
        if not reports:
            raise ValueError("at least one research report is required")
        scored = [(score_report(r), r) for r in reports]
        scored.sort(
            key=lambda pair: (
                pair[0].total,
                pair[0].obligation_coverage,
                pair[0].citation_traceability,
                pair[0].lineage_score,
                -pair[0].unresolved_penalty,
            ),
            reverse=True,
        )
        score, report = scored[0]
        return report, score
