from contracts.science_contracts import consume_quantum_reference_control, consume_provenance_graph
import pytest

def test_quantum_control_not_novel_physics():
    x=consume_quantum_reference_control({"benchmark_id":"b","passed":True,"science_status":"STANDARD_QM_REFERENCE_CONTROL","chsh_absolute_value":2.8,"tsirelson_bound":2.828,"experimental_result":False,"novel_physics_claim":False})
    assert x["novel_physics_claim"] is False

def test_provenance_graph_not_wrongdoing_inference():
    p={"snapshot_id":"s","nodes":2,"edges":1,"records_scanned":2,"nodes_sha256":"1"*64,"edges_sha256":"2"*64,"evidence_sha256":"3"*64,"relationship_semantics_preserved":True,"wrongdoing_inference_authority":False,"identity_claim_authority":False}
    x=consume_provenance_graph(p)
    assert x["wrongdoing_inference_authority"] is False

def test_graph_cannot_self_promote_wrongdoing():
    p={"snapshot_id":"s","nodes":2,"edges":1,"records_scanned":2,"nodes_sha256":"1"*64,"edges_sha256":"2"*64,"evidence_sha256":"3"*64,"relationship_semantics_preserved":True,"wrongdoing_inference_authority":True,"identity_claim_authority":False}
    with pytest.raises(ValueError): consume_provenance_graph(p)
