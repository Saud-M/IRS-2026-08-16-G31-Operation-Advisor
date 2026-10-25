"""Benchmark runner comparing Decision Tree, Random Forest, KNN, MLP, and Bayesian Networks.

Generates evaluation tables, confusion matrices, and feature importances.
Saves trained models to models/scenario_classifiers.pkl.
"""

import os
import json
import pandas as pd
from src.learning.classifiers import ScenarioClassifierSuite
from src.learning.bayesian_network import ProcessBayesianNetwork


def run_benchmark():
    data_path = os.path.join("data", "simulation", "telemetry_timeseries.csv")
    if not os.path.exists(data_path):
        print(f"Error: {data_path} not found. Run data_generator first.")
        return

    print("Loading telemetry dataset...")
    df = pd.read_csv(data_path)
    print(f"Loaded {len(df)} rows across {df['scenario_label'].nunique()} scenario classes.")

    print("\nTraining supervised classifier suite (KNN, Decision Tree, Random Forest, MLP)...")
    suite = ScenarioClassifierSuite(random_state=42)
    evaluations = suite.train(df)

    print("\n" + "=" * 65)
    print(f"{'Model':<18} | {'Macro F1':<10} | {'Precision':<10} | {'Recall':<10}")
    print("=" * 65)
    for name, ev in evaluations.items():
        print(f"{name:<18} | {ev.macro_f1:<10.4f} | {ev.precision:<10.4f} | {ev.recall:<10.4f}")
    print("=" * 65)

    print("\nTop 5 Random Forest Gini Feature Importances:")
    importances = suite.get_feature_importances()
    for rank, (feat, imp) in enumerate(list(importances.items())[:5], 1):
        print(f"  {rank}. {feat:<20}: {imp:.4f}")

    # Save models
    model_path = os.path.join("models", "scenario_classifiers.pkl")
    suite.save(model_path)
    print(f"\nTrained models serialized to: {model_path}")

    # Evaluate Bayesian Network
    print("\nEvaluating Bayesian Belief Network on fault scenarios:")
    bn = ProcessBayesianNetwork()
    test_cases = [
        ("PCV Stiction Closed", {"SYM_HIGH_PRESSURE": 1, "SYM_LOW_GAS_FLOW": 1}),
        ("Foaming Carryover", {"SYM_HIGH_DEMISTER_DP": 1, "SYM_HIGH_SCRUBBER_LEVEL": 1}),
        ("Compressor Surge", {"SYM_HIGH_VIBRATION": 1, "SYM_LOW_GAS_FLOW": 1}),
        ("Emulsion Layer Drift", {"SYM_LOW_INTERFACE": 1}),
    ]

    for name, ev in test_cases:
        res = bn.infer(ev)
        top = res.ranked_hypotheses[0]
        print(f"  • Case: {name:<22} -> Top Hypothesis: {top.hypothesis_id} ({top.posterior_prob*100:.1f}%) | Entropy: {res.shannon_entropy:.2f} bits | Next Check: {res.most_informative_next_check}")

    print("\nBenchmark completed successfully.")


if __name__ == "__main__":
    run_benchmark()
