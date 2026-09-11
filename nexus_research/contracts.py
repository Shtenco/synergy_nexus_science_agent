from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


class ClaimStatus(str, Enum):
    OPEN = "OPEN"
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    REPRODUCED = "REPRODUCED"
    FALSIFIED = "FALSIFIED"
    UNKNOWN = "UNKNOWN"


class QueryIntent(str, Enum):
    PRIMARY = "PRIMARY"
    CONFIRM = "CONFIRM"
    CONTRADICT = "CONTRADICT"
    RECENCY = "RECENCY"
    REPLICATION = "REPLICATION"
    DEFINITIONS = "DEFINITIONS"
    DATA = "DATA"


@dataclass(frozen=True)
class ResearchQuestion:
    text: str
    scope: str = ""
    freshness_days: Optional[int] = None
    required_domains: Tuple[str, ...] = ()
    user_constraints: Tuple[str, ...] = ()


@dataclass(frozen=True)
class SemanticObligation:
    obligation_id: str
    description: str
    required: bool = True
    satisfied: bool = False


@dataclass(frozen=True)
class SearchQuery:
    query_id: str
    text: str
    intent: QueryIntent
    obligation_ids: Tuple[str, ...] = ()
    hypothesis_id: str = ""
    priority: float = 0.5


@dataclass(frozen=True)
class SearchHit:
    query_id: str
    url: str
    title: str
    snippet: str = ""
    published_at: Optional[str] = None
    provider: str = ""


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    url: str
    title: str
    text: str
    content_sha256: str
    retrieved_at: str
    published_at: Optional[str] = None
    source_type: str = "web"
    domain: str = ""
    lineage_id: str = ""
    is_primary: bool = False
    quality_score: float = 0.5


@dataclass(frozen=True)
class Claim:
    claim_id: str
    text: str
    obligation_ids: Tuple[str, ...] = ()
    status: ClaimStatus = ClaimStatus.OPEN
    confidence: float = 0.0


@dataclass(frozen=True)
class EvidenceItem:
    evidence_id: str
    claim_id: str
    source_id: str
    relation: str  # SUPPORTS | CONTRADICTS | FALSIFIES | REPLICATES
    quote: str = ""
    confidence: float = 0.5
    independently_verified: bool = False


@dataclass
class ResearchRound:
    index: int
    queries: List[SearchQuery] = field(default_factory=list)
    source_ids: List[str] = field(default_factory=list)
    new_claim_ids: List[str] = field(default_factory=list)
    unresolved_obligations: List[str] = field(default_factory=list)
    expected_information_gain: float = 0.0
    stop_reason: str = ""


@dataclass(frozen=True)
class CompletenessCertificate:
    obligation_coverage: float
    primary_source_coverage: float
    contradiction_search_done: bool
    falsification_attempted: bool
    independent_lineages: int
    unresolved_high_value_claims: int
    freshness_satisfied: bool
    citation_traceability: float

    @property
    def eligible_to_finalize(self) -> bool:
        return (
            self.obligation_coverage >= 1.0
            and self.contradiction_search_done
            and self.falsification_attempted
            and self.independent_lineages >= 2
            and self.unresolved_high_value_claims == 0
            and self.freshness_satisfied
            and self.citation_traceability >= 1.0
        )


@dataclass
class ResearchReport:
    question: ResearchQuestion
    claims: List[Claim]
    evidence: List[EvidenceItem]
    sources: List[SourceRecord]
    rounds: List[ResearchRound]
    certificate: CompletenessCertificate
    summary: str
    open_questions: List[str] = field(default_factory=list)
    search_queries: List[SearchQuery] = field(default_factory=list)
    source_manifest: Dict[str, str] = field(default_factory=dict)
