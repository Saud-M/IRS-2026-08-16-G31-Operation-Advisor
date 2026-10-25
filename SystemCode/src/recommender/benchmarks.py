"""Recommender Benchmarks: Association Rule Mining & Matrix Factorization.

Implements course-aligned recommendation experiments:
1. Association Rule Mining (Apriori): Discovers frequent co-occurring diagnostic checks
   and corrective action sequences (Support, Confidence, Lift).
2. Case-by-Action Matrix Factorization (SVD): Evaluates latent interaction factors
   where historical incidents serve as contexts.
3. Cold-Start Assessment: Demonstrates fallback from collaborative filtering to
   content/graph-based recommender when new incident cases have zero prior action history.
"""

from dataclasses import dataclass
import itertools
from typing import Dict, Any, List, Set, Tuple, Optional
import numpy as np
import pandas as pd
from sklearn.decomposition import TruncatedSVD
from sklearn.metrics.pairwise import cosine_similarity


@dataclass
class AssociationRule:
    antecedent: Tuple[str, ...]
    consequent: Tuple[str, ...]
    support: float
    confidence: float
    lift: float


class AssociationRuleMiner:
    """Discovers frequent itemsets and association rules from historical incident logs."""

    def __init__(self, min_support: float = 0.15, min_confidence: float = 0.60):
        self.min_support = min_support
        self.min_confidence = min_confidence
        self.rules: List[AssociationRule] = []

    def fit(self, transactions: List[List[str]]) -> List[AssociationRule]:
        """Mine frequent pairs and generate high-confidence association rules."""
        n_tx = len(transactions)
        if n_tx == 0:
            return []

        # Count 1-itemsets
        item_counts: Dict[str, int] = {}
        for tx in transactions:
            for item in set(tx):
                item_counts[item] = item_counts.get(item, 0) + 1

        frequent_items = {item: count for item, count in item_counts.items() if (count / n_tx) >= self.min_support}

        # Count 2-itemsets
        pair_counts: Dict[Tuple[str, str], int] = {}
        for tx in transactions:
            unique_items = sorted(list(set(tx) & set(frequent_items.keys())))
            for i1, i2 in itertools.combinations(unique_items, 2):
                pair = (i1, i2)
                pair_counts[pair] = pair_counts.get(pair, 0) + 1

        self.rules = []
        for (i1, i2), count in pair_counts.items():
            support_pair = count / n_tx
            if support_pair < self.min_support:
                continue

            supp_i1 = frequent_items[i1] / n_tx
            supp_i2 = frequent_items[i2] / n_tx

            # Rule 1: i1 -> i2
            conf_1_2 = support_pair / supp_i1
            lift_1_2 = conf_1_2 / supp_i2
            if conf_1_2 >= self.min_confidence:
                self.rules.append(
                    AssociationRule(
                        antecedent=(i1,),
                        consequent=(i2,),
                        support=round(support_pair, 3),
                        confidence=round(conf_1_2, 3),
                        lift=round(lift_1_2, 3),
                    )
                )

            # Rule 2: i2 -> i1
            conf_2_1 = support_pair / supp_i2
            lift_2_1 = conf_2_1 / supp_i1
            if conf_2_1 >= self.min_confidence:
                self.rules.append(
                    AssociationRule(
                        antecedent=(i2,),
                        consequent=(i1,),
                        support=round(support_pair, 3),
                        confidence=round(conf_2_1, 3),
                        lift=round(lift_2_1, 3),
                    )
                )

        self.rules.sort(key=lambda r: (r.lift, r.confidence), reverse=True)
        return self.rules


class MatrixFactorizationRecommender:
    """Case-by-Action matrix factorization with cold-start fallback handling."""

    def __init__(self, n_components: int = 3):
        self.n_components = n_components
        self.svd = TruncatedSVD(n_components=n_components, random_state=42)
        self.case_ids: List[str] = []
        self.action_ids: List[str] = []
        self.R: Optional[np.ndarray] = None
        self.R_reconstructed: Optional[np.ndarray] = None
        self.item_similarity_matrix: Optional[np.ndarray] = None

    def fit(self, interaction_df: pd.DataFrame) -> None:
        """Fit latent factor SVD on Case-by-Action interaction matrix."""
        # Rows = Cases, Columns = Actions, Values = Relevance / Frequency
        pivot = interaction_df.pivot_table(index="case_id", columns="action_id", values="weight", fill_value=0.0)
        self.case_ids = list(pivot.index)
        self.action_ids = list(pivot.columns)
        self.R = pivot.values

        # If components exceed matrix dimension, clip to min dimension
        max_comps = min(self.R.shape) - 1
        n_comps = max(1, min(self.n_components, max_comps))
        self.svd.n_components = n_comps

        # Fit SVD and reconstruct matrix
        U_sigma = self.svd.fit_transform(self.R)
        self.R_reconstructed = np.dot(U_sigma, self.svd.components_)

        # Calculate item-item cosine similarity
        self.item_similarity_matrix = cosine_similarity(self.R.T)

    def recommend_for_case(self, case_id: str, top_k: int = 3) -> Dict[str, Any]:
        """Generate recommendations for a historical case or detect cold start."""
        if self.R_reconstructed is None or case_id not in self.case_ids:
            return {
                "case_id": case_id,
                "is_cold_start": True,
                "recommendations": [],
                "strategy": "Fallback to Content- and Graph-Based Recommender",
            }

        case_idx = self.case_ids.index(case_id)
        predicted_scores = self.R_reconstructed[case_idx]

        ranked_indices = np.argsort(predicted_scores)[::-1][:top_k]
        recs = [
            {"action_id": self.action_ids[idx], "latent_score": round(float(predicted_scores[idx]), 3)}
            for idx in ranked_indices
        ]

        return {
            "case_id": case_id,
            "is_cold_start": False,
            "recommendations": recs,
            "strategy": "Collaborative Latent Factor Filtering (SVD)",
        }


def evaluate_recommenders() -> Dict[str, Any]:
    """Execute evaluation benchmark for Apriori and SVD matrix factorization."""
    transactions = [
        ["CHK_01_LOCAL_PCV_STEM", "CHK_02_PCV_AIR_SUPPLY", "ACT_01_SWITCH_MANUAL_BYPASS"],
        ["CHK_01_LOCAL_PCV_STEM", "ACT_01_SWITCH_MANUAL_BYPASS"],
        ["CHK_01_LOCAL_PCV_STEM", "CHK_02_PCV_AIR_SUPPLY", "ACT_01_SWITCH_MANUAL_BYPASS"],
        ["CHK_03_DEMISTER_DP", "ACT_02_INJECT_ANTIFOAM"],
        ["CHK_03_DEMISTER_DP", "ACT_02_INJECT_ANTIFOAM", "ACT_05_PINCH_WELLHEAD_CHOKE"],
        ["CHK_01_LOCAL_PCV_STEM", "CHK_02_PCV_AIR_SUPPLY"],
        ["CHK_01_LOCAL_PCV_STEM", "ACT_01_SWITCH_MANUAL_BYPASS"],
        ["CHK_04_ASV_STROKE", "ACT_03_OPEN_ASV"],
        ["CHK_04_ASV_STROKE", "ACT_03_OPEN_ASV", "ACT_07_DRAIN_SCRUBBER_MANUAL"],
        ["CHK_05_INTERFACE_SAMPLE", "ACT_04_INCREASE_DEMULSIFIER"],
    ]

    miner = AssociationRuleMiner(min_support=0.15, min_confidence=0.50)
    rules = miner.fit(transactions)

    case_data = [
        {"case_id": "CASE_H01_01", "action_id": "ACT_01_SWITCH_MANUAL_BYPASS", "weight": 5.0},
        {"case_id": "CASE_H01_01", "action_id": "CHK_01_LOCAL_PCV_STEM", "weight": 4.0},
        {"case_id": "CASE_H01_02", "action_id": "ACT_01_SWITCH_MANUAL_BYPASS", "weight": 5.0},
        {"case_id": "CASE_H01_02", "action_id": "CHK_02_PCV_AIR_SUPPLY", "weight": 4.0},
        {"case_id": "CASE_H03_01", "action_id": "ACT_02_INJECT_ANTIFOAM", "weight": 5.0},
        {"case_id": "CASE_H03_01", "action_id": "CHK_03_DEMISTER_DP", "weight": 4.0},
        {"case_id": "CASE_H03_02", "action_id": "ACT_02_INJECT_ANTIFOAM", "weight": 5.0},
        {"case_id": "CASE_H04_01", "action_id": "ACT_03_OPEN_ASV", "weight": 5.0},
        {"case_id": "CASE_H04_01", "action_id": "CHK_04_ASV_STROKE", "weight": 4.0},
        {"case_id": "CASE_H04_02", "action_id": "ACT_03_OPEN_ASV", "weight": 5.0},
        {"case_id": "CASE_H05_01", "action_id": "ACT_04_INCREASE_DEMULSIFIER", "weight": 5.0},
        {"case_id": "CASE_H05_02", "action_id": "ACT_04_INCREASE_DEMULSIFIER", "weight": 5.0},
        {"case_id": "CASE_H06_01", "action_id": "ACT_05_PINCH_WELLHEAD_CHOKE", "weight": 5.0},
        {"case_id": "CASE_H06_02", "action_id": "ACT_05_PINCH_WELLHEAD_CHOKE", "weight": 5.0},
    ]
    df = pd.DataFrame(case_data)
    mf = MatrixFactorizationRecommender(n_components=3)
    mf.fit(df)

    hits = 0
    total = len(mf.case_ids)
    for c_id in mf.case_ids:
        actual_top_action = df[df["case_id"] == c_id].sort_values("weight", ascending=False).iloc[0]["action_id"]
        res = mf.recommend_for_case(c_id, top_k=3)
        rec_ids = [r["action_id"] for r in res["recommendations"]]
        if actual_top_action in rec_ids:
            hits += 1

    hit_rate = hits / max(1, total)

    return {
        "association_rules": {
            "rules_count": len(rules),
            "top_rules": [
                {
                    "antecedent": list(r.antecedent),
                    "consequent": list(r.consequent),
                    "confidence": r.confidence,
                    "lift": r.lift,
                }
                for r in rules[:3]
            ],
        },
        "svd_matrix_factorization": {
            "cases_count": total,
            "actions_count": len(mf.action_ids),
            "hit_rate@3": round(hit_rate, 4),
            "cold_start_sample_recs": 1 if mf.recommend_for_case("NEW_CASE_UNKNOWN")["is_cold_start"] else 0,
        },
    }
