import pytest

from nexus_science_agent import CommercializationCandidate, ScienceContractError


def test_falsified_hypothesis_cannot_be_commercialized():
    with pytest.raises(ScienceContractError):
        CommercializationCandidate(
            candidate_id="c1",
            technology="x",
            hypothesis_status="FALSIFIED",
            trl=4,
            reproduction_status="INTERNAL",
            evidence_refs=("exp:1",),
            target_industries=("manufacturing",),
        )


def test_high_trl_requires_reproduction():
    with pytest.raises(ScienceContractError):
        CommercializationCandidate(
            candidate_id="c1",
            technology="x",
            hypothesis_status="SUPPORTED",
            trl=6,
            reproduction_status="NONE",
            evidence_refs=("exp:1",),
            target_industries=("manufacturing",),
        )


def test_independent_reproduction_flag():
    candidate = CommercializationCandidate(
        candidate_id="c1",
        technology="x",
        hypothesis_status="SUPPORTED",
        trl=7,
        reproduction_status="INDEPENDENT",
        evidence_refs=("exp:1", "rep:1"),
        target_industries=("manufacturing",),
    )
    assert candidate.independently_reproduced
