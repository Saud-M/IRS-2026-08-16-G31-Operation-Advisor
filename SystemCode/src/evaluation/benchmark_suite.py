"""Comprehensive System Benchmark Evaluation Suite for Operation Advisor.

Executes quantitative evaluations across the 5 core AI pillars:
1. Supervised Learning: Evaluates DT, RF, KNN, and MLP on sensor telemetry (Macro F1, Accuracy).
2. Bayesian Uncertainty: Evaluates exact posterior belief, Shannon entropy reduction, and Brier score.
3. Response Planning: Evaluates A* search latency, step optimality, and dynamic replanning time.
4. Recommendation: Evaluates Hit-Rate@K and safety interlock filtering efficiency.
5. Cognitive NLU: Evaluates intent recognition accuracy and slot extraction precision/recall.
6. RAG Grounding: Evaluates document retrieval precision, citation resolution, and zero-hallucination rate.
7. Safety Barrier: Assesses 100% rejection rate for prohibited automated writes and interlock violations.
8. Dynamic Walkthrough: Executes full end-to-end simulation across all 6 operational scenarios.
"""

from dataclasses import dataclass, asdict
from datetime import datetime
import json
import os
import time
from typing import Dict, Any, List, Optional

import numpy as np

# Core Modules
from src.simulation_bridge.process_model import SeparatorCompressorTrain
from src.simulation_bridge.scenarios import ScenarioType, ScenarioInjector, FaultConfig
from src.learning.classifiers import ScenarioClassifierSuite
from src.learning.bayesian_network import ProcessBayesianNetwork
from src.planning.astar_planner import AStarPlanner, PlantPlanState
from src.planning.ga_optimizer import GeneticAlgorithmOptimizer
from src.recommender.action_recommender import ContentGraphRecommender
from src.recommender.benchmarks import evaluate_recommenders
from src.cognitive.nlu_parser import NLUParser, TaskIntent
from src.cognitive.working_memory import WorkingMemory
from src.cognitive.dialogue_manager import DialogueManager
from src.rag.rag_engine import RAGEngine
from src.validation.pipeline import ValidationPipeline


@dataclass
class EvaluationBenchmarkResult:
    timestamp: str
    classifier_metrics: Dict[str, Any]
    bayesian_metrics: Dict[str, Any]
    planning_metrics: Dict[str, Any]
    recommender_metrics: Dict[str, Any]
    nlu_metrics: Dict[str, Any]
    rag_metrics: Dict[str, Any]
    safety_metrics: Dict[str, Any]
    scenario_walkthrough_results: Dict[str, Any]
    all_targets_met: bool


class SystemBenchmarkSuite:
    """Orchestrates comprehensive quantitative benchmarks against NUS ISS criteria."""

    def __init__(self, data_dir: Optional[str] = None):
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        self.data_dir = data_dir or os.path.join(root_dir, "data")
        self.output_dir = os.path.join(self.data_dir, "cases")
        os.makedirs(self.output_dir, exist_ok=True)

    def evaluate_classifiers(self) -> Dict[str, Any]:
        """Benchmark supervised fault classifiers (KNN, Decision Tree, Random Forest, MLP)."""
        import pandas as pd
        csv_path = os.path.join(self.data_dir, "simulation", "telemetry_timeseries.csv")
        df = pd.read_csv(csv_path)

        suite = ScenarioClassifierSuite(random_state=42)
        suite.train(df)

        metrics = {}
        for name, ev in suite.evaluations.items():
            metrics[name] = {
                "accuracy": round(float(ev.report.get("accuracy", ev.macro_f1)), 4),
                "macro_f1": round(float(ev.macro_f1), 4),
            }

        best_model = max(metrics.keys(), key=lambda k: metrics[k]["macro_f1"])
        return {
            "models": metrics,
            "best_model": best_model,
            "best_macro_f1": metrics[best_model]["macro_f1"],
            "target_met": bool(metrics[best_model]["macro_f1"] >= 0.92),
        }

    def evaluate_bayesian_network(self) -> Dict[str, Any]:
        """Benchmark Bayesian Belief Network exact posterior updates and entropy reduction."""
        bbn = ProcessBayesianNetwork()

        # Prior distribution entropy
        prior_probs = list(bbn.priors.values())
        prior_entropy = -sum(p * np.log2(p) for p in prior_probs if p > 0)

        # Posterior under overpressure evidence
        evidence_h01 = {"SYM_HIGH_PRESSURE": 1, "SYM_LOW_GAS_FLOW": 1}
        res_h01 = bbn.infer(evidence_h01)
        post_entropy_h01 = res_h01.shannon_entropy
        ig_h01 = prior_entropy - post_entropy_h01

        # Posterior under foaming evidence
        evidence_h03 = {"SYM_HIGH_DEMISTER_DP": 1, "SYM_HIGH_SCRUBBER_LEVEL": 1}
        res_h03 = bbn.infer(evidence_h03)
        post_entropy_h03 = res_h03.shannon_entropy
        ig_h03 = prior_entropy - post_entropy_h03

        # Compute Brier score proxy across discrete scenarios
        brier_scores = [
            (1.0 - res_h01.ranked_hypotheses[0].posterior_prob) ** 2,
            (1.0 - res_h03.ranked_hypotheses[0].posterior_prob) ** 2,
        ]
        mean_brier = float(np.mean(brier_scores))

        return {
            "prior_entropy_bits": round(float(prior_entropy), 3),
            "h01_posterior_prob": round(float(res_h01.ranked_hypotheses[0].posterior_prob), 4),
            "h01_entropy_reduction_bits": round(float(ig_h01), 3),
            "h03_posterior_prob": round(float(res_h03.ranked_hypotheses[0].posterior_prob), 4),
            "h03_entropy_reduction_bits": round(float(ig_h03), 3),
            "mean_brier_score": round(mean_brier, 4),
            "target_met": bool(ig_h01 >= 0.40 and ig_h03 >= 0.40),
        }

    def evaluate_planning(self) -> Dict[str, Any]:
        """Benchmark A* state-space search planning latency and dynamic replanning."""
        planner = AStarPlanner()

        # Initial overpressure state requiring remediation
        initial_state = PlantPlanState(
            pressure_status="CRITICAL",
            liquid_status="NORMAL",
            compressor_status="RUNNING",
            pcv_status="CLOSED_STUCK",
            antifoam_active=False,
            permit_granted=True,
        )

        latencies = []
        for _ in range(50):
            t0 = time.perf_counter()
            plan_res = planner.plan(initial_state)
            latencies.append((time.perf_counter() - t0) * 1000.0)

        mean_latency_ms = float(np.mean(latencies))
        p95_latency_ms = float(np.percentile(latencies, 95))

        # Dynamic replanning test on blocked action
        t0_replan = time.perf_counter()
        replan_res = planner.replan_with_blocked_node(initial_state, "ACT_01_SWITCH_MANUAL_BYPASS")
        replan_latency_ms = (time.perf_counter() - t0_replan) * 1000.0

        return {
            "mean_planning_latency_ms": round(mean_latency_ms, 2),
            "p95_planning_latency_ms": round(p95_latency_ms, 2),
            "plan_steps_count": len(plan_res.steps),
            "plan_is_feasible": plan_res.is_feasible,
            "replan_feasible_under_block": replan_res.is_feasible,
            "replan_latency_ms": round(replan_latency_ms, 2),
            "target_met": bool(mean_latency_ms < 200.0 and plan_res.is_feasible),
        }

    def evaluate_recommender(self) -> Dict[str, Any]:
        """Benchmark Content/Graph Recommender and Collaborative SVD Matrix Factorization."""
        rec_res = evaluate_recommenders()
        hit_rate_at_3 = rec_res["svd_matrix_factorization"]["hit_rate@3"]

        return {
            "apriori_rules_count": rec_res["association_rules"]["rules_count"],
            "svd_hit_rate_at_3": round(float(hit_rate_at_3), 4),
            "cold_start_fallback_working": rec_res["svd_matrix_factorization"]["cold_start_sample_recs"] > 0,
            "target_met": bool(hit_rate_at_3 >= 0.80),
        }

    def evaluate_nlu(self) -> Dict[str, Any]:
        """Benchmark natural language understanding, intent detection, and slot extraction."""
        nlu = NLUParser()

        test_cases = [
            ("Why is separator V-101 pressure rising at 35.5 barg?", TaskIntent.DIAGNOSE, "V-101", "SYM_HIGH_PRESSURE"),
            ("Please generate the response plan for PCV-101 failure", TaskIntent.PLAN, "PCV-101", None),
            ("Check instrument air pressure to PCV-101 positioner", TaskIntent.VERIFY_CHECK, "PCV-101", None),
            ("Explain the operating procedure for demister foaming", TaskIntent.EXPLAIN, None, "SYM_HIGH_DEMISTER_DP"),
            ("Please prepare the shift handover report for incoming crew", TaskIntent.HANDOVER, None, None),
            ("What is the current operating status of K-101?", TaskIntent.STATUS_QUERY, "K-101", None),
        ]

        intent_correct = 0
        slot_hits = 0
        total_slots = 0

        for text, exp_intent, exp_asset, exp_sym in test_cases:
            slots, _ = nlu.parse(text)
            if slots.task_intent == exp_intent:
                intent_correct += 1

            if exp_asset:
                total_slots += 1
                if slots.asset_tag == exp_asset:
                    slot_hits += 1

            if exp_sym:
                total_slots += 1
                if exp_sym in slots.symptoms or slots.symptom == exp_sym:
                    slot_hits += 1

        intent_acc = intent_correct / len(test_cases)
        slot_acc = slot_hits / max(1, total_slots)

        return {
            "intent_accuracy": round(float(intent_acc), 4),
            "slot_accuracy": round(float(slot_acc), 4),
            "test_cases_count": len(test_cases),
            "target_met": (intent_acc >= 0.90 and slot_acc >= 0.85),
        }

    def evaluate_rag(self) -> Dict[str, Any]:
        """Benchmark technical document retrieval, passage grounding, and anti-hallucination verification."""
        rag = RAGEngine()

        # Query procedural search
        matches = rag.query_procedures("PCV-101 stuck overpressure manual bypass valve", top_k=2)
        has_citations = len(matches) > 0 and all(m.citation_tag.startswith("[") for m in matches)

        # Grounded explanation verification
        exp = rag.explain_hypothesis("H01", "PCV-101 Stuck Closed")
        valid_citations, missing = rag.verify_citations(exp.explanation_text)

        # Anti-hallucination verification
        fake_text = "Refer to non-existent standard [SOP-FAKE Section 999]."
        fake_valid, fake_missing = rag.verify_citations(fake_text)

        return {
            "indexed_passages_count": len(rag.indexer.passages),
            "search_retrieval_working": has_citations,
            "explanation_citations_verified": valid_citations and len(missing) == 0,
            "hallucination_detection_working": (not fake_valid and len(fake_missing) > 0),
            "target_met": (len(rag.indexer.passages) >= 8 and valid_citations and not fake_valid),
        }

    def evaluate_safety_barrier(self) -> Dict[str, Any]:
        """Benchmark safety barrier rejection of prohibited actions and interlock violations."""
        pipeline = ValidationPipeline()

        # 1. Prohibited automated DCS write attempt
        prohibited_plan = [{"action_id": "WRITE_DCS_CONTROLLER_SP", "target_equipment": "PCV-101"}]
        rep1 = pipeline.validate_cycle(
            telemetry={"PT-101": 35.0},
            candidate_plan=prohibited_plan,
        )

        # 2. Spurious flaring attempt under normal pressure
        spurious_flare_plan = [{"action_id": "ACT_06_DIVERT_TO_FLARE", "target_equipment": "V-101"}]
        rep2 = pipeline.validate_cycle(
            telemetry={"PT-101": 31.0},
            candidate_plan=spurious_flare_plan,
        )

        # 3. Thermodynamic inversion (interface > total level)
        rep3 = pipeline.validate_cycle(
            telemetry={"LT-101": 30.0, "LT-102": 60.0},
        )

        all_rejected = (rep1.status == "REJECTED" and rep2.status == "REJECTED" and rep3.status == "REJECTED")

        return {
            "prohibited_dcs_write_rejected": rep1.status == "REJECTED",
            "spurious_flaring_rejected": rep2.status == "REJECTED",
            "thermodynamic_inversion_rejected": rep3.status == "REJECTED",
            "rejection_rate_pct": 100.0 if all_rejected else 0.0,
            "target_met": all_rejected,
        }

    def run_scenario_walkthroughs(self) -> Dict[str, Any]:
        """Execute full dynamic end-to-end walkthroughs across all 6 operational scenarios."""
        scenarios = [
            ("NOMINAL", ScenarioType.NOMINAL, "H07", 0.0, "What is the current operating status of separator V-101?"),
            ("PCV_STICTION", ScenarioType.PCV_STICTION, "H01", 0.9, "Why is separator V-101 pressure high at 36.2 barg with low gas flow?"),
            ("LIQUID_CARRYOVER", ScenarioType.LIQUID_CARRYOVER, "H03", 0.85, "Why is separator V-101 experiencing foaming carryover and high dp?"),
            ("COMPRESSOR_SURGE", ScenarioType.COMPRESSOR_SURGE, "H04", 0.85, "Why is compressor K-101 experiencing high vibration and surge?"),
            ("EMULSION_PAD", ScenarioType.EMULSION_PAD, "H05", 0.8, "Why is separator V-101 showing low interface level reading with emulsion?"),
            ("SLUG_INFLUX", ScenarioType.SLUG_INFLUX, "H06", 0.85, "Why is separator V-101 experiencing high level and high pressure from slug influx?"),
        ]

        walkthrough_results = {}
        all_passed = True

        for name, sc_type, expected_hypo, sev, query in scenarios:
            train = SeparatorCompressorTrain()
            if sc_type != ScenarioType.NOMINAL:
                config = FaultConfig(
                    scenario_type=sc_type,
                    start_time_sec=5.0,
                    duration_sec=120.0,
                    severity=sev,
                    parameters={"stuck_position": 0.08} if sc_type == ScenarioType.PCV_STICTION else {},
                )
                injector = ScenarioInjector(config)
                for _ in range(60):
                    injector.apply(train)
                    train.step(dt=1.0)
                if sc_type == ScenarioType.PCV_STICTION:
                    train.state.shaft_vibration_mms = 1.8
            else:
                for _ in range(60):
                    train.step(dt=1.0)

            snap = train.snapshot()
            p101 = float(snap.get("PT-101", 31.0))
            telemetry = {
                "PT-101": round(p101, 2),
                "PT-102": round(p101 - 0.7, 2),
                "PT-103": round(p101 * 2.4, 2),
                "LT-101": round(float(snap.get("LT-101", 50.0)), 2),
                "LT-102": round(float(snap.get("LT-102", 25.0)), 2),
                "LT-103": round(float(snap.get("V102_scrubber_level", 12.0)), 2),
                "FT-101": round(float(snap.get("FT-101", 68000.0)), 1),
                "DPIT-101": round(float(snap.get("DP-101", 0.022)), 4),
                "VT-101": round(float(snap.get("ST-101", 1.45)), 2),
            }

            # Initialize working memory and dialogue cycle
            wm = WorkingMemory(incident_title=f"Walkthrough {name}")
            wm.update_telemetry(telemetry)
            mgr = DialogueManager(working_memory=wm)

            resp = mgr.process_text_input(query)

            is_correct = (resp.top_hypothesis == expected_hypo)
            if not is_correct:
                all_passed = False

            # Verify Shift Handover export
            rag = RAGEngine()
            handover = rag.generate_shift_handover(wm)

            walkthrough_results[name] = {
                "expected_hypothesis": expected_hypo,
                "diagnosed_hypothesis": resp.top_hypothesis,
                "confidence_pct": resp.confidence_pct,
                "correct_diagnosis": is_correct,
                "response_plan_steps": len(resp.active_plan),
                "citations_count": len(resp.citations),
                "handover_generated": len(handover["markdown"]) > 500,
            }

        return {
            "scenarios": walkthrough_results,
            "all_scenarios_passed": all_passed,
        }

    def run_full_benchmark(self) -> EvaluationBenchmarkResult:
        """Run all quantitative benchmarks and write persistent report to JSON."""
        print("Running Supervised Learning Benchmarks...")
        clf_metrics = self.evaluate_classifiers()

        print("Running Bayesian Belief Network Benchmarks...")
        bbn_metrics = self.evaluate_bayesian_network()

        print("Running A* Response Planning Benchmarks...")
        plan_metrics = self.evaluate_planning()

        print("Running Recommendation Benchmarks...")
        rec_metrics = self.evaluate_recommender()

        print("Running Cognitive NLU Benchmarks...")
        nlu_metrics = self.evaluate_nlu()

        print("Running RAG & Grounding Benchmarks...")
        rag_metrics = self.evaluate_rag()

        print("Running Safety Barrier Compliance Benchmarks...")
        safety_metrics = self.evaluate_safety_barrier()

        print("Running 6-Scenario Dynamic Physics Walkthroughs...")
        walkthrough_metrics = self.run_scenario_walkthroughs()

        all_met = (
            clf_metrics["target_met"]
            and bbn_metrics["target_met"]
            and plan_metrics["target_met"]
            and rec_metrics["target_met"]
            and nlu_metrics["target_met"]
            and rag_metrics["target_met"]
            and safety_metrics["target_met"]
            and walkthrough_metrics["all_scenarios_passed"]
        )

        result = EvaluationBenchmarkResult(
            timestamp=datetime.now().isoformat(),
            classifier_metrics=clf_metrics,
            bayesian_metrics=bbn_metrics,
            planning_metrics=plan_metrics,
            recommender_metrics=rec_metrics,
            nlu_metrics=nlu_metrics,
            rag_metrics=rag_metrics,
            safety_metrics=safety_metrics,
            scenario_walkthrough_results=walkthrough_metrics,
            all_targets_met=all_met,
        )

        # Save to JSON report
        out_file = os.path.join(self.output_dir, "evaluation_benchmark_report.json")
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(asdict(result), f, indent=2)

        return result


if __name__ == "__main__":
    suite = SystemBenchmarkSuite()
    res = suite.run_full_benchmark()
    print("=" * 70)
    print("SYSTEM BENCHMARK EVALUATION COMPLETE")
    print(f"All NUS ISS Targets Met: {res.all_targets_met}")
    print("=" * 70)
