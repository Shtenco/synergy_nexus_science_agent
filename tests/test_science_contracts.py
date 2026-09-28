import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "contracts" / "science_contracts.py"
spec = importlib.util.spec_from_file_location("science_contracts", PATH)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)


def test_nexus_is_advisory_only_for_science():
    task = mod.science_task_from_nexus({
        "task_type": "SCIENCE",
        "model_id": "nexus-v18",
        "proposal": {"question": "does X reproduce?"},
        "confidence": 0.62,
        "limitations": ["proposal only"],
    })
    assert task["authorization"] is False
    assert task["requires_falsification"] is True


def test_evidence_package_enforces_source_binding():
    src = mod.source_record(source_id="S1", locator="paper:1", content=b"paper bytes")
    payload = mod.evidence_package_payload(
        research_question="Does X reproduce?",
        claims=[{
            "claim_id": "C1",
            "text": "Measured result",
            "epistemic_status": "MEASURED",
            "source_ids": ["S1"],
        }],
        sources=[src],
        status="REPRODUCED",
        reproduction_command="python reproduce.py",
    )
    assert payload["status"] == "REPRODUCED"
    assert payload["claims"][0]["epistemic_status"] == "MEASURED"


def test_unknown_source_fails_closed():
    with pytest.raises(ValueError):
        mod.evidence_package_payload(
            research_question="Q",
            claims=[{
                "claim_id": "C1", "text": "x",
                "epistemic_status": "DERIVED", "source_ids": ["missing"]
            }],
            sources=[],
            status="CANDIDATE",
        )


def test_reproduced_requires_command():
    with pytest.raises(ValueError):
        mod.evidence_package_payload(
            research_question="Q",
            claims=[],
            sources=[],
            status="REPRODUCED",
        )
