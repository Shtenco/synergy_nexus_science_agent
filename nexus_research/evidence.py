from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import replace
from urllib.parse import urlparse
from typing import Dict, Iterable, List, Mapping, Sequence, Set, Tuple

from .contracts import Claim, ClaimStatus, EvidenceItem, SourceRecord


def source_lineage(url: str) -> str:
    """Cheap default lineage key; production adapters may provide publisher/citation lineage."""
    host = (urlparse(url).hostname or "unknown").lower()
    host = host[4:] if host.startswith("www.") else host
    parts = host.split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return host


def content_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


class SourceRegistry:
    """Content-addressed source registry with URL/content deduplication."""

    def __init__(self) -> None:
        self._by_id: Dict[str, SourceRecord] = {}
        self._content_to_id: Dict[str, str] = {}
        self._url_to_id: Dict[str, str] = {}

    def add(self, source: SourceRecord) -> Tuple[str, bool]:
        if source.content_sha256 in self._content_to_id:
            return self._content_to_id[source.content_sha256], False
        if source.url in self._url_to_id:
            return self._url_to_id[source.url], False
        lineage = source.lineage_id or source_lineage(source.url)
        row = replace(source, lineage_id=lineage)
        self._by_id[row.source_id] = row
        self._content_to_id[row.content_sha256] = row.source_id
        self._url_to_id[row.url] = row.source_id
        return row.source_id, True

    def values(self) -> List[SourceRecord]:
        return list(self._by_id.values())

    def get(self, source_id: str) -> SourceRecord:
        return self._by_id[source_id]


class EvidenceGraph:
    """Typed claim/source graph used for support, contradiction and falsification."""

    def __init__(self) -> None:
        self.claims: Dict[str, Claim] = {}
        self.evidence: Dict[str, EvidenceItem] = {}
        self.by_claim: Dict[str, List[str]] = defaultdict(list)

    def add_claim(self, claim: Claim) -> None:
        current = self.claims.get(claim.claim_id)
        if current is None or claim.confidence >= current.confidence:
            self.claims[claim.claim_id] = claim

    def add_evidence(self, row: EvidenceItem) -> None:
        self.evidence[row.evidence_id] = row
        if row.evidence_id not in self.by_claim[row.claim_id]:
            self.by_claim[row.claim_id].append(row.evidence_id)

    def relations(self, claim_id: str) -> List[EvidenceItem]:
        return [self.evidence[eid] for eid in self.by_claim.get(claim_id, ())]

    def independent_lineages(self, claim_id: str, sources: Mapping[str, SourceRecord]) -> Set[str]:
        return {
            sources[row.source_id].lineage_id
            for row in self.relations(claim_id)
            if row.source_id in sources
        }

    def score_claim(self, claim_id: str, sources: Mapping[str, SourceRecord]) -> Claim:
        claim = self.claims[claim_id]
        rows = self.relations(claim_id)
        support = 0.0
        contradiction = 0.0
        support_lineages: Set[str] = set()
        contradiction_lineages: Set[str] = set()
        for row in rows:
            src = sources.get(row.source_id)
            if src is None:
                continue
            # Repeated same-lineage sources have diminishing marginal authority.
            quality = max(0.0, min(1.0, src.quality_score))
            weight = max(0.0, min(1.0, row.confidence)) * quality
            relation = row.relation.upper()
            if relation in {"SUPPORTS", "REPLICATES"}:
                if src.lineage_id not in support_lineages:
                    support += weight
                    support_lineages.add(src.lineage_id)
                else:
                    support += 0.20 * weight
            elif relation in {"CONTRADICTS", "FALSIFIES", "FAILS_TO_REPLICATE"}:
                if src.lineage_id not in contradiction_lineages:
                    contradiction += weight
                    contradiction_lineages.add(src.lineage_id)
                else:
                    contradiction += 0.20 * weight

        total = support + contradiction
        if total <= 1e-12:
            return replace(claim, status=ClaimStatus.UNKNOWN, confidence=0.0)
        margin = abs(support - contradiction) / total
        if contradiction > support and contradiction_lineages:
            status = ClaimStatus.FALSIFIED if any(
                r.relation.upper() == "FALSIFIES" for r in rows
            ) else ClaimStatus.CONTRADICTED
        elif support > contradiction and support_lineages:
            status = ClaimStatus.REPRODUCED if any(
                r.relation.upper() == "REPLICATES" for r in rows
            ) else ClaimStatus.SUPPORTED
        else:
            status = ClaimStatus.UNKNOWN
        return replace(claim, status=status, confidence=margin)

    def rescored_claims(self, sources: Sequence[SourceRecord]) -> List[Claim]:
        mapping = {s.source_id: s for s in sources}
        return [self.score_claim(cid, mapping) for cid in self.claims]
