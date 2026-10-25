"""Unit and Integration Tests for Recommender Subsystem (Sprint 4).
Verifies content/graph recommendations, safety interlocks, Apriori mining, and SVD matrix factorization.
"""

import pandas as pd
import pytest
from src.recommender.action_recommender import ContentGraphRecommender, RiskLevel
from src.recommender.benchmarks import AssociationRuleMiner, MatrixFactorizationRecommender


@pytest.fixture
def recommender():
    return ContentGraphRecommender()


def test_content_graph_recommender_ranking(recommender):
    """Verify that strong belief in H01 promotes PCV manual bypass."""
    beliefs = {"H01": 0.85, "H07": 0.15}
    plant_state = {"permit_to_work": True, "pcv101_isolation_closed": False}

    recs = recommender.recommend_actions(beliefs, plant_state=plant_state, top_k=3)
    assert len(recs) > 0
    top_rec = recs[0]
    assert top_rec.action_id == "ACT_01_SWITCH_MANUAL_BYPASS"
    assert top_rec.eligible is True
    assert top_rec.score > 0.50


def test_recommender_safety_interlock_filtering(recommender):
    """Verify that actions violating safety interlocks are flagged as ineligible."""
    beliefs = {"H01": 0.90}
    # Permit to work revoked
    plant_state = {"permit_to_work": False}

    recs = recommender.recommend_actions(beliefs, plant_state=plant_state)
    bypass_rec = next((r for r in recs if r.action_id == "ACT_01_SWITCH_MANUAL_BYPASS"), None)
    assert bypass_rec is not None
    assert bypass_rec.eligible is False
    assert any("Permit to Work" in reason for reason in bypass_rec.blocking_reasons)


def test_association_rule_mining():
    """Verify discovery of frequent co-occurring operator checks and actions."""
    transactions = [
        ["CHK_01", "CHK_02", "ACT_01"],
        ["CHK_01", "ACT_01"],
        ["CHK_01", "CHK_02", "ACT_01"],
        ["CHK_03", "ACT_02"],
        ["CHK_03", "ACT_02", "ACT_05"],
        ["CHK_01", "CHK_02"],
        ["CHK_01", "ACT_01"],
    ]

    miner = AssociationRuleMiner(min_support=0.25, min_confidence=0.60)
    rules = miner.fit(transactions)

    assert len(rules) > 0
    # Rule CHK_02 -> ACT_01 or CHK_01 -> ACT_01 should exist
    antecedents = [r.antecedent[0] for r in rules]
    assert "CHK_01" in antecedents or "CHK_02" in antecedents


def test_matrix_factorization_and_cold_start():
    """Verify SVD collaborative latent factor scoring and cold-start detection."""
    data = [
        {"case_id": "CASE_01", "action_id": "ACT_01", "weight": 5.0},
        {"case_id": "CASE_01", "action_id": "CHK_01", "weight": 4.0},
        {"case_id": "CASE_02", "action_id": "ACT_02", "weight": 5.0},
        {"case_id": "CASE_02", "action_id": "CHK_03", "weight": 5.0},
        {"case_id": "CASE_03", "action_id": "ACT_01", "weight": 4.0},
        {"case_id": "CASE_03", "action_id": "CHK_02", "weight": 3.0},
        {"case_id": "CASE_04", "action_id": "ACT_03", "weight": 5.0},
    ]
    df = pd.DataFrame(data)

    mf = MatrixFactorizationRecommender(n_components=2)
    mf.fit(df)

    # Known case recommendation
    known_res = mf.recommend_for_case("CASE_01")
    assert known_res["is_cold_start"] is False
    assert len(known_res["recommendations"]) > 0

    # Cold start case (brand new incident)
    cold_res = mf.recommend_for_case("NEW_CASE_UNKNOWN_99")
    assert cold_res["is_cold_start"] is True
    assert "Fallback to Content" in cold_res["strategy"]
