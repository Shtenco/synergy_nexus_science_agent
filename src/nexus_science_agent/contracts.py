from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal


class ScienceContractError(ValueError):
    pass


@dataclass(frozen=True)
class CommercializationCandidate:
    candidate_id: str
    technology: str
    hypothesis_status: Literal["HYPOTHESIS", "SUPPORTED", "FALSIFIED", "INCONCLUSIVE"]
    trl: int
    reproduction_status: Literal["NONE", "INTERNAL", "INDEPENDENT"]
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    target_industries: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not 1 <= self.trl <= 9:
            raise ScienceContractError("TRL must be between 1 and 9")
        if not self.evidence_refs:
            raise ScienceContractError("commercialization handoff requires evidence")
        if not self.target_industries:
            raise ScienceContractError("commercialization handoff requires a target industry")
        if self.hypothesis_status == "FALSIFIED":
            raise ScienceContractError("falsified hypothesis cannot be commercialized")
        if self.trl >= 6 and self.reproduction_status == "NONE":
            raise ScienceContractError("TRL>=6 requires at least internal reproduction")

    @property
    def independently_reproduced(self) -> bool:
        return self.reproduction_status == "INDEPENDENT"

    def as_payload(self) -> dict:
        payload = asdict(self)
        payload["evidence_refs"] = list(self.evidence_refs)
        payload["target_industries"] = list(self.target_industries)
        return payload
