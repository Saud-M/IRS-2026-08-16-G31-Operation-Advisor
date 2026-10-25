"""Unit and Integration Tests for Machine Learning & Uncertainty Module (Sprint 3).
Verifies supervised classifiers (KNN, Decision Tree, Random Forest, MLP) and
Bayesian Belief Network inference, entropy quantification, and Value of Information.
"""

import os
import pandas as pd
import pytest
from src.learning.classifiers import ScenarioClassifierSuite
from src.learning.bayesian_network import ProcessBayesianNetwork, PGMPY_AVAILABLE


@pytest.fixture(scope="module")
def telemetry_df():
    data_path = os.path.join("data", "simulation", "telemetry_timeseries.csv")
    if not os.path.exists(data_path):
        pytest.skip(f"Telemetry dataset not found at {data_path}")
    return pd.read_csv(data_path)


@pytest.fixture(scope="module")
def trained_suite(telemetry_df):
    suite = ScenarioClassifierSuite(random_state=42)
    suite.train(telemetry_df)
    return suite


@pytest.fixture
def bayes_net():
    return ProcessBayesianNetwork()


def test_classifiers_training_and_evaluation(trained_suite):
    """Verify that all classifiers train and exceed baseline F1 score of 0.85."""
    evaluations = trained_suite.evaluations

    assert "knn" in evaluations
    assert "decision_tree" in evaluations
    assert "random_forest" in evaluations
    assert "mlp" in evaluations

    # Random forest should achieve high F1 score on simulation data
    rf_eval = evaluations["random_forest"]
    assert rf_eval.macro_f1 >= 0.88, f"Random Forest F1 below target: {rf_eval.macro_f1}"
    assert rf_eval.precision >= 0.85
    assert rf_eval.recall >= 0.85

    # Check feature importances
    importances = trained_suite.get_feature_importances()
    assert len(importances) > 0
    # PT-101, DP-101, or ST-101 should be among top features
    top_features = list(importances.keys())[:5]
    assert any(tag in top_features for tag in ["PT-101", "DP-101", "ST-101", "surge_margin_pct"])


def test_classifiers_prediction(telemetry_df, trained_suite):
    """Verify live single-row prediction pipeline."""
    surge_row = telemetry_df[
        (telemetry_df["scenario_label"] == "COMPRESSOR_K101_SURGE") & (telemetry_df["fault_active"] == 1)
    ].iloc[10]
    sample = surge_row.to_dict()

    pred = trained_suite.predict(sample, model_name="random_forest")
    assert "predicted_scenario" in pred
    assert pred["predicted_scenario"] == "COMPRESSOR_K101_SURGE"
    assert pred["confidence"] > 0.60


def test_bayesian_network_prior_consistency(bayes_net):
    """Verify that empty evidence returns the prior belief distribution."""
    res = bayes_net.infer(evidence={})
    assert len(res.ranked_hypotheses) == 7
    # Baseline prior for H07 should be highest initially
    assert res.ranked_hypotheses[0].hypothesis_id == "H07"
    # Entropy should be near maximal
    assert res.normalized_entropy > 0.90


def test_bayesian_network_overpressure_evidence(bayes_net):
    """Verify that High Pressure + Low Gas Flow shifts belief to H01 (PCV Stuck Closed)."""
    evidence = {
        "SYM_HIGH_PRESSURE": 1,
        "SYM_LOW_GAS_FLOW": 1,
        "SYM_HIGH_DEMISTER_DP": 0,
        "SYM_HIGH_VIBRATION": 0,
    }
    res = bayes_net.infer(evidence)
    top_hypo = res.ranked_hypotheses[0]
    assert top_hypo.hypothesis_id == "H01", f"Expected H01, got {top_hypo.hypothesis_id}"
    assert top_hypo.posterior_prob > 0.70, f"Expected posterior > 0.70, got {top_hypo.posterior_prob}"
    # Entropy should drop significantly
    assert res.normalized_entropy < 0.60


def test_bayesian_network_foaming_carryover_evidence(bayes_net):
    """Verify that High Demister DP + High Scrubber Level shifts belief to H03 (Foaming)."""
    evidence = {
        "SYM_HIGH_DEMISTER_DP": 1,
        "SYM_HIGH_SCRUBBER_LEVEL": 1,
        "SYM_HIGH_VIBRATION": 0,
        "SYM_HIGH_PRESSURE": 0,
    }
    res = bayes_net.infer(evidence)
    top_hypo = res.ranked_hypotheses[0]
    assert top_hypo.hypothesis_id == "H03", f"Expected H03, got {top_hypo.hypothesis_id}"
    assert top_hypo.posterior_prob > 0.80


def test_bayesian_network_information_gain(bayes_net):
    """Verify that Value of Information identifies the most informative unobserved check."""
    # When High Pressure is observed, we want to know whether Flow is low (H01) or Level is high (H06)
    evidence = {"SYM_HIGH_PRESSURE": 1}
    res = bayes_net.infer(evidence)

    assert len(res.missing_evidence_gain) > 0
    assert res.most_informative_next_check is not None
    # Information gain should be positive
    best_gain = res.missing_evidence_gain[res.most_informative_next_check]
    assert best_gain > 0.05


def test_pgmpy_model_conversion(bayes_net):
    """Verify conversion to pgmpy DiscreteBayesianNetwork if pgmpy is installed."""
    if not PGMPY_AVAILABLE:
        pytest.skip("pgmpy not available")

    model = bayes_net.to_pgmpy_model()
    assert model is not None
    assert model.check_model()
    assert model.has_node("Fault")
    assert model.has_node("SYM_HIGH_PRESSURE")
