import pytest

from nexus_science_agent.source_quality_v3 import (
    SourceAssessment,
    SourceQualityError,
    canonicalize_arxiv,
    canonicalize_doi,
    canonicalize_repository,
    verify_source_assessment,
)


D = "1" * 64
M = "2" * 64


def test_identifiers_are_canonicalized():
    assert canonicalize_doi("DOI:10.1000/ABC.DEF") == "https://doi.org/10.1000/abc.def"
    assert canonicalize_arxiv("arXiv:2401.12345") == "https://arxiv.org/abs/2401.12345"
    assert canonicalize_repository("https://github.com/Shtenco/agi_nexus/tree/main") == "https://github.com/Shtenco/agi_nexus"


def test_primary_peer_reviewed_non_retracted_is_high_confidence_eligible():
    assessment = SourceAssessment(
        source_id="paper-1", source_kind="DOI_ARTICLE",
        canonical_locator="https://doi.org/10.1000/test", document_content_sha256=D,
        metadata_evidence_digest=M, primary_source=True, peer_review_status="PEER_REVIEWED",
        retraction_status="NOT_RETRACTED_AT_CHECK", code_available=True, data_available=False,
    )
    payload = assessment.artifact()
    assert payload["gate_status"] == "HIGH_CONFIDENCE_ELIGIBLE"
    assert payload["scientific_truth_authority"] == "NONE"
    assert payload["automatic_evidence_score_authority"] == "NONE"
    verify_source_assessment(payload)


def test_preprint_is_eligible_with_caveats_not_auto_downgraded_to_false():
    assessment = SourceAssessment(
        source_id="preprint", source_kind="ARXIV_PREPRINT",
        canonical_locator="https://arxiv.org/abs/2401.12345", document_content_sha256=D,
        metadata_evidence_digest=M, primary_source=True, peer_review_status="PREPRINT",
        retraction_status="NOT_RETRACTED_AT_CHECK", code_available=False, data_available=False,
    )
    assert assessment.gate_status == "ELIGIBLE_WITH_CAVEATS"


def test_retracted_source_is_blocked():
    assessment = SourceAssessment(
        source_id="paper-2", source_kind="DOI_ARTICLE",
        canonical_locator="https://doi.org/10.1000/retracted", document_content_sha256=D,
        metadata_evidence_digest=M, primary_source=True, peer_review_status="PEER_REVIEWED",
        retraction_status="RETRACTED", code_available=False, data_available=False,
    )
    assert assessment.gate_status == "BLOCKED_RETRACTED"


def test_unknown_metadata_remains_unknown():
    assessment = SourceAssessment(
        source_id="web", source_kind="WEB_DOCUMENT",
        canonical_locator="https://example.com/article", document_content_sha256=D,
        metadata_evidence_digest=M, primary_source=False, peer_review_status="UNKNOWN",
        retraction_status="UNKNOWN", code_available=False, data_available=False,
    )
    assert assessment.gate_status == "UNKNOWN_METADATA"


def test_fresh_hash_cannot_turn_retracted_source_into_high_confidence():
    payload = SourceAssessment(
        source_id="paper-3", source_kind="DOI_ARTICLE",
        canonical_locator="https://doi.org/10.1000/retracted2", document_content_sha256=D,
        metadata_evidence_digest=M, primary_source=True, peer_review_status="PEER_REVIEWED",
        retraction_status="RETRACTED", code_available=False, data_available=False,
    ).artifact()
    payload["gate_status"] = "HIGH_CONFIDENCE_ELIGIBLE"
    import hashlib, json
    body = dict(payload); body.pop("digest")
    payload["digest"] = hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    with pytest.raises(SourceQualityError, match="deterministic classification"):
        verify_source_assessment(payload)


def test_non_https_or_noncanonical_repository_is_rejected():
    with pytest.raises(SourceQualityError):
        canonicalize_repository("http://github.com/Shtenco/agi_nexus")
