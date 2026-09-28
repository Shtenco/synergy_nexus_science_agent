from contracts.science_contracts import consume_constraint_benchmark, consume_model_consistency
import pytest

def test_constraint_benchmark_stays_measured_not_break_claim():
    x=consume_constraint_benchmark({"benchmark_id":"b","problem_family":"SHA","information_gain_bits":8,"epistemic_status":"MEASURED","cryptographic_break_claim":False})
    assert x["break_claim"] is False
    assert x["requires_independent_reproduction"] is True

def test_model_consistency_stays_noncausal():
    x=consume_model_consistency({"experiment_id":"e","table_graph_gate_pass":True,"epistemic_status":"DERIVED","observed_physical_effect":False,"causal_claim_authority":False})
    assert x["observed_physical_effect"] is False

def test_model_cannot_claim_observed_effect():
    with pytest.raises(ValueError):
        consume_model_consistency({"experiment_id":"e","table_graph_gate_pass":True,"epistemic_status":"DERIVED","observed_physical_effect":True,"causal_claim_authority":False})
