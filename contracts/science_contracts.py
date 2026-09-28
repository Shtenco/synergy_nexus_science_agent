from __future__ import annotations

from hashlib import sha256
from typing import Any


AI_PROPOSAL_CONTRACT_ID = "synergy.ai.proposal/v1"
CONTRACT_ID = "synergy.science.evidence-package/v1"
AUTHORITY = "science_research"

EPISTEMIC_STATUSES = {
    "SOURCE", "MEASURED", "DERIVED", "SIMULATION",
    "HYPOTHESIS", "FALSIFIED", "UNRESOLVED",
}
PACKAGE_STATUSES = {"OPEN", "CANDIDATE", "FALSIFIED", "REPRODUCED"}


def science_task_from_nexus(payload: dict[str, Any]) -> dict[str, Any]:
    task_type = str(payload.get("task_type", "")).upper()
    if task_type not in {"SCIENCE", "GENERAL"}:
        raise ValueError(f"NEXUS proposal is not a science task: {task_type}")
    confidence = float(payload.get("confidence", -1))
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("invalid NEXUS confidence")
    limitations = payload.get("limitations")
    if not isinstance(limitations, list) or not limitations:
        raise ValueError("science task requires explicit NEXUS limitations")
    proposal = payload.get("proposal")
    if not isinstance(proposal, dict) or not proposal:
        raise ValueError("science task proposal must be a non-empty object")
    return {
        "source": "NEXUS_ADVISORY",
        "model_id": str(payload.get("model_id", "")),
        "proposal": dict(proposal),
        "confidence": confidence,
        "limitations": list(limitations),
        "authorization": False,
        "requires_independent_sources": True,
        "requires_falsification": True,
    }


def source_record(*, source_id: str, locator: str, content: bytes) -> dict[str, str]:
    if not source_id or not locator or not content:
        raise ValueError("source_id, locator and source bytes are required")
    return {
        "source_id": source_id,
        "locator": locator,
        "sha256": sha256(content).hexdigest(),
    }


def evidence_package_payload(
    *,
    research_question: str,
    claims: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    status: str,
    reproduction_command: str | None = None,
) -> dict[str, Any]:
    if not research_question.strip():
        raise ValueError("research_question required")
    package_status = status.upper()
    if package_status not in PACKAGE_STATUSES:
        raise ValueError("unsupported package status")

    source_ids: set[str] = set()
    normalized_sources = []
    for source in sources:
        sid = str(source.get("source_id", ""))
        locator = str(source.get("locator", ""))
        digest = str(source.get("sha256", "")).lower()
        if not sid or sid in source_ids:
            raise ValueError("source ids must be non-empty and unique")
        if not locator or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError(f"invalid source record: {sid}")
        source_ids.add(sid)
        normalized_sources.append({"source_id": sid, "locator": locator, "sha256": digest})

    claim_ids: set[str] = set()
    normalized_claims = []
    for claim in claims:
        cid = str(claim.get("claim_id", ""))
        text = str(claim.get("text", ""))
        epistemic = str(claim.get("epistemic_status", "")).upper()
        refs = [str(x) for x in claim.get("source_ids", [])]
        if not cid or cid in claim_ids:
            raise ValueError("claim ids must be non-empty and unique")
        if not text:
            raise ValueError(f"claim {cid} has empty text")
        if epistemic not in EPISTEMIC_STATUSES:
            raise ValueError(f"claim {cid} has invalid epistemic status")
        missing = [sid for sid in refs if sid not in source_ids]
        if missing:
            raise ValueError(f"claim {cid} references unknown sources: {missing}")
        if epistemic in {"SOURCE", "MEASURED", "DERIVED", "FALSIFIED"} and not refs:
            raise ValueError(f"{epistemic} claim {cid} requires source_ids")
        claim_ids.add(cid)
        normalized_claims.append({
            "claim_id": cid,
            "text": text,
            "epistemic_status": epistemic,
            "source_ids": refs,
        })

    if package_status == "REPRODUCED" and not reproduction_command:
        raise ValueError("REPRODUCED package requires reproduction_command")
    if package_status == "FALSIFIED" and not any(
        c["epistemic_status"] == "FALSIFIED" for c in normalized_claims
    ):
        raise ValueError("FALSIFIED package must contain a FALSIFIED claim")

    return {
        "research_question": research_question.strip(),
        "claims": normalized_claims,
        "sources": normalized_sources,
        "status": package_status,
        "reproduction_command": reproduction_command,
    }
