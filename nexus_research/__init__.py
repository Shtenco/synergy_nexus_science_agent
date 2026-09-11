"""NEXUS R8.3 Research Cortex.

Scientific web-research orchestration layer. Search providers are subordinate
transport organs; evidence, contradiction, completeness and provenance decide
what may enter the final research brief.
"""

from .contracts import (
    Claim,
    EvidenceItem,
    ResearchQuestion,
    ResearchReport,
    SearchHit,
    SearchQuery,
    SourceRecord,
)
from .engine import ResearchCortex, ResearchPolicy

__all__ = [
    "Claim",
    "EvidenceItem",
    "ResearchQuestion",
    "ResearchReport",
    "SearchHit",
    "SearchQuery",
    "SourceRecord",
    "ResearchCortex",
    "ResearchPolicy",
]
