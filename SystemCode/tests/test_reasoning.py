"""Unit and Integration Tests for Machine Reasoning Module (Sprint 2).
Verifies Knowledge Graph queries, forward chaining rule triggers, and backward chaining goal evaluation.
"""

import pytest
from src.reasoning.knowledge_graph import KnowledgeGraph
from src.reasoning.forward_chaining import ForwardChainingEngine
from src.reasoning.backward_chaining import BackwardChainingEngine, GoalStatus


@pytest.fixture
def kg():
    return KnowledgeGraph()


@pytest.fixture
def fwd_engine():
    return ForwardChainingEngine()


@pytest.fixture
def bwd_engine(kg):
    return BackwardChainingEngine(knowledge_graph=kg)


def test_knowledge_graph_structure(kg):
    """Verify that ontology nodes and edges load properly into NetworkX."""
    summary = kg.summary()
    assert summary["total_nodes"] >= 20, f"Expected >= 20 nodes, got {summary['total_nodes']}"
    assert summary["total_edges"] >= 25, f"Expected >= 25 edges, got {summary['total_edges']}"
    assert "Asset" in summary["node_types"]
    assert "Hypothesis" in summary["node_types"]
    assert "Check" in summary["node_types"]
    assert "DocumentPassage" in summary["node_types"]


def test_knowledge_graph_queries(kg):
    """Verify relational graph traversals."""
    # Query hypotheses related to high pressure symptom
    hypos = kg.get_hypotheses_for_symptoms(["SYM_HIGH_PRESSURE"])
    assert len(hypos) > 0
    h_ids = [h["id"] for h in hypos]
    assert "H01" in h_ids, "H01 should be strongly indicated by high pressure"

    # Query checks for H01
    checks = kg.get_checks_for_hypothesis("H01")
    chk_ids = [c["id"] for c in checks]
    assert "CHK_01_LOCAL_PCV_STEM" in chk_ids

    # Query citations for H01
    citations = kg.get_citations_for_hypothesis("H01")
    doc_ids = [d["id"] for d in citations]
    assert "SOP-V101-SEC2" in doc_ids


def test_forward_chaining_pcv_stuck_closed(fwd_engine):
    """Verify that high pressure + low export flow fires H01 rule."""
    facts = {
        "PT-101": 35.2,
        "FT-101": 52000.0,
        "PCV-101_pos": 0.12,
        "LT-101": 50.0,
    }
    result = fwd_engine.infer(facts)
    assert "SYM_HIGH_PRESSURE" in result.active_symptoms
    assert "SYM_LOW_GAS_FLOW" in result.active_symptoms
    assert "H01" in result.candidate_hypotheses
    assert len(result.rule_traces) >= 2


def test_forward_chaining_foaming_carryover(fwd_engine):
    """Verify that elevated demister DP and scrubber accumulation trigger H03."""
    facts = {
        "DP-101": 0.52,
        "V102_scrubber_level": 28.0,
        "LT-101": 72.0,
    }
    result = fwd_engine.infer(facts)
    assert "SYM_HIGH_DEMISTER_DP" in result.active_symptoms
    assert "SYM_HIGH_SCRUBBER_LEVEL" in result.active_symptoms
    assert "H03" in result.candidate_hypotheses


def test_forward_chaining_nominal_fallback(fwd_engine):
    """Verify that nominal operational facts infer H07 (Nominal)."""
    facts = {
        "PT-101": 30.1,
        "LT-101": 50.2,
        "LT-102": 24.8,
        "DP-101": 0.11,
        "ST-101": 1.9,
        "FT-101": 90500.0,
        "V102_scrubber_level": 5.0,
    }
    result = fwd_engine.infer(facts)
    assert len(result.active_symptoms) == 0
    assert result.candidate_hypotheses == ["H07"]


def test_backward_chaining_evaluation_pending_evidence(bwd_engine):
    """Verify goal evaluation requests operator checks when facts are missing."""
    facts = {"PT-101": 35.5}
    known_symptoms = {"SYM_HIGH_PRESSURE"}

    res = bwd_engine.evaluate_hypothesis("H01", facts, known_symptoms)
    assert res.status == GoalStatus.PENDING_EVIDENCE
    assert res.verification_score > 0.0
    assert len(res.prioritized_checks) > 0
    assert res.prioritized_checks[0].check_id == "CHK_01_LOCAL_PCV_STEM"


def test_backward_chaining_evaluation_refutation(bwd_engine):
    """Verify goal evaluation transitions to REFUTED if a check fails."""
    facts = {"PT-101": 35.5}
    known_symptoms = {"SYM_HIGH_PRESSURE"}
    completed_checks = {
        "CHK_01_LOCAL_PCV_STEM": {"positive": False, "comment": "Valve stem is freely moving at 80% stroke"}
    }

    res = bwd_engine.evaluate_hypothesis("H01", facts, known_symptoms, completed_checks)
    assert res.status == GoalStatus.REFUTED
    assert res.verification_score < 0.1
