"""Unit and Integration Tests for System Benchmark Suite (Sprint 8).

Verifies that the implemented system meets all quantitative success criteria
defined in the project proposal and master plan.
"""

import pytest
from src.evaluation.benchmark_suite import SystemBenchmarkSuite


@pytest.fixture(scope="module")
def benchmark_suite():
    return SystemBenchmarkSuite()


def test_benchmark_classifiers(benchmark_suite):
    """Verify supervised classification models exceed Macro F1 target >= 0.92."""
    res = benchmark_suite.evaluate_classifiers()
    assert res["target_met"] is True
    assert res["best_macro_f1"] >= 0.92
    assert "random_forest" in res["models"]
    assert res["models"]["random_forest"]["macro_f1"] >= 0.92


def test_benchmark_bayesian_network(benchmark_suite):
    """Verify exact Bayesian posterior inference achieves Shannon entropy reduction >= 0.40 bits."""
    res = benchmark_suite.evaluate_bayesian_network()
    assert res["target_met"] is True
    assert res["h01_entropy_reduction_bits"] >= 0.40
    assert res["h03_entropy_reduction_bits"] >= 0.40
    assert res["mean_brier_score"] < 0.25


def test_benchmark_planning_latency(benchmark_suite):
    """Verify bounded A* search latency < 200ms and dynamic replanning feasibility."""
    res = benchmark_suite.evaluate_planning()
    assert res["target_met"] is True
    assert res["mean_planning_latency_ms"] < 200.0
    assert res["plan_is_feasible"] is True
    assert res["replan_feasible_under_block"] is True


def test_benchmark_recommenders(benchmark_suite):
    """Verify collaborative and graph recommenders achieve Hit-Rate@3 >= 0.80."""
    res = benchmark_suite.evaluate_recommender()
    assert res["target_met"] is True
    assert res["svd_hit_rate_at_3"] >= 0.80
    assert res["apriori_rules_count"] > 0


def test_benchmark_nlu(benchmark_suite):
    """Verify cognitive NLU intent recognition >= 90% and slot filling >= 85%."""
    res = benchmark_suite.evaluate_nlu()
    assert res["target_met"] is True
    assert res["intent_accuracy"] >= 0.90
    assert res["slot_accuracy"] >= 0.85


def test_benchmark_rag_grounding(benchmark_suite):
    """Verify procedural RAG citations are 100% verified against indexed corpus without hallucination."""
    res = benchmark_suite.evaluate_rag()
    assert res["target_met"] is True
    assert res["explanation_citations_verified"] is True
    assert res["hallucination_detection_working"] is True


def test_benchmark_safety_barrier(benchmark_suite):
    """Verify safety validation gate achieves 100% rejection on unauthorized writes and interlock violations."""
    res = benchmark_suite.evaluate_safety_barrier()
    assert res["target_met"] is True
    assert res["rejection_rate_pct"] == 100.0


def test_benchmark_scenario_walkthroughs(benchmark_suite):
    """Verify dynamic end-to-end physics walkthrough across all 6 operational scenarios."""
    res = benchmark_suite.run_scenario_walkthroughs()
    assert res["all_scenarios_passed"] is True
    assert len(res["scenarios"]) == 6
    for name, data in res["scenarios"].items():
        assert data["correct_diagnosis"] is True
        assert data["handover_generated"] is True
