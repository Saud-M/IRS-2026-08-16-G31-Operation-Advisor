"""Bayesian Network for Probabilistic Fault Hypothesis Ranking & Uncertainty Quantification.

Implements exact Bayesian inference over competing oil and gas fault hypotheses:
1. Prior and conditional probabilities estimated from simulated process operating distributions.
2. Exact posterior probability distribution P(Fault_i | Evidence).
3. Shannon Entropy computation to score diagnostic uncertainty and ambiguity.
4. Value of Information (Information Gain) analysis identifying which unobserved test
   will maximize uncertainty reduction.
5. Bidirectional compatibility with pgmpy DiscreteBayesianNetwork and native numpy matrix operations.
"""

from dataclasses import dataclass, field
import math
from typing import Dict, Any, List, Optional, Tuple
import numpy as np

try:
    from pgmpy.models import DiscreteBayesianNetwork
    from pgmpy.factors.discrete import TabularCPD
    from pgmpy.inference import VariableElimination
    PGMPY_AVAILABLE = True
except ImportError:
    PGMPY_AVAILABLE = False


FAULT_STATES = ["H01", "H02", "H03", "H04", "H05", "H06", "H07"]

FAULT_DESCRIPTIONS = {
    "H01": "PCV-101 Stuck Closed / Air Failure",
    "H02": "PCV-101 Stuck Open",
    "H03": "Separator Foaming & Demister Carryover",
    "H04": "Compressor K-101 Aerodynamic Surge",
    "H05": "Emulsion Rag Layer & LT-102 Drift",
    "H06": "Wellhead Transient Slug Influx",
    "H07": "Nominal Steady-State Operation",
}

OBSERVABLE_SYMPTOMS = [
    "SYM_HIGH_PRESSURE",
    "SYM_LOW_PRESSURE",
    "SYM_HIGH_LEVEL",
    "SYM_LOW_INTERFACE",
    "SYM_HIGH_DEMISTER_DP",
    "SYM_HIGH_VIBRATION",
    "SYM_LOW_GAS_FLOW",
    "SYM_HIGH_SCRUBBER_LEVEL",
]


@dataclass
class HypothesisBelief:
    hypothesis_id: str
    description: str
    posterior_prob: float
    prior_prob: float
    likelihood_ratio: float


@dataclass
class BayesianInferenceResult:
    ranked_hypotheses: List[HypothesisBelief]
    shannon_entropy: float        # in bits
    normalized_entropy: float     # [0.0 = total certainty, 1.0 = maximal ambiguity]
    active_evidence: Dict[str, int]
    missing_evidence_gain: Dict[str, float]  # symptom -> expected entropy reduction
    most_informative_next_check: Optional[str]


class ProcessBayesianNetwork:
    """Bayesian Belief Network for diagnosing root-cause fault hypotheses."""

    def __init__(self):
        # Simulator prior belief distribution (equal baseline distribution over operational scenarios)
        self.priors: Dict[str, float] = {
            "H01": 0.15,
            "H02": 0.08,
            "H03": 0.15,
            "H04": 0.12,
            "H05": 0.13,
            "H06": 0.12,
            "H07": 0.25, # Nominal has higher base prior
        }

        # Conditional Probability Table: P(Symptom = 1 | Fault = H_i)
        # Based on process physics and simulation sensitivity
        self.cpt: Dict[str, Dict[str, float]] = {
            # H01: PCV Stuck Closed
            "H01": {
                "SYM_HIGH_PRESSURE": 0.96,
                "SYM_LOW_PRESSURE": 0.01,
                "SYM_HIGH_LEVEL": 0.15,
                "SYM_LOW_INTERFACE": 0.05,
                "SYM_HIGH_DEMISTER_DP": 0.12,
                "SYM_HIGH_VIBRATION": 0.08,
                "SYM_LOW_GAS_FLOW": 0.92,
                "SYM_HIGH_SCRUBBER_LEVEL": 0.08,
            },
            # H02: PCV Stuck Open
            "H02": {
                "SYM_HIGH_PRESSURE": 0.01,
                "SYM_LOW_PRESSURE": 0.95,
                "SYM_HIGH_LEVEL": 0.08,
                "SYM_LOW_INTERFACE": 0.04,
                "SYM_HIGH_DEMISTER_DP": 0.05,
                "SYM_HIGH_VIBRATION": 0.05,
                "SYM_LOW_GAS_FLOW": 0.05,
                "SYM_HIGH_SCRUBBER_LEVEL": 0.02,
            },
            # H03: Separator Foaming Carryover
            "H03": {
                "SYM_HIGH_PRESSURE": 0.20,
                "SYM_LOW_PRESSURE": 0.02,
                "SYM_HIGH_LEVEL": 0.88,
                "SYM_LOW_INTERFACE": 0.12,
                "SYM_HIGH_DEMISTER_DP": 0.97,
                "SYM_HIGH_VIBRATION": 0.25,
                "SYM_LOW_GAS_FLOW": 0.35,
                "SYM_HIGH_SCRUBBER_LEVEL": 0.94,
            },
            # H04: Compressor Surge
            "H04": {
                "SYM_HIGH_PRESSURE": 0.25,
                "SYM_LOW_PRESSURE": 0.05,
                "SYM_HIGH_LEVEL": 0.05,
                "SYM_LOW_INTERFACE": 0.02,
                "SYM_HIGH_DEMISTER_DP": 0.30,
                "SYM_HIGH_VIBRATION": 0.98,
                "SYM_LOW_GAS_FLOW": 0.88,
                "SYM_HIGH_SCRUBBER_LEVEL": 0.10,
            },
            # H05: Emulsion Pad & LT-102 Drift
            "H05": {
                "SYM_HIGH_PRESSURE": 0.05,
                "SYM_LOW_PRESSURE": 0.02,
                "SYM_HIGH_LEVEL": 0.45,
                "SYM_LOW_INTERFACE": 0.95,
                "SYM_HIGH_DEMISTER_DP": 0.08,
                "SYM_HIGH_VIBRATION": 0.04,
                "SYM_LOW_GAS_FLOW": 0.05,
                "SYM_HIGH_SCRUBBER_LEVEL": 0.04,
            },
            # H06: Wellhead Slugging
            "H06": {
                "SYM_HIGH_PRESSURE": 0.82,
                "SYM_LOW_PRESSURE": 0.10,
                "SYM_HIGH_LEVEL": 0.92,
                "SYM_LOW_INTERFACE": 0.35,
                "SYM_HIGH_DEMISTER_DP": 0.70,
                "SYM_HIGH_VIBRATION": 0.20,
                "SYM_LOW_GAS_FLOW": 0.40,
                "SYM_HIGH_SCRUBBER_LEVEL": 0.65,
            },
            # H07: Nominal Normal Operation
            "H07": {
                "SYM_HIGH_PRESSURE": 0.02,
                "SYM_LOW_PRESSURE": 0.02,
                "SYM_HIGH_LEVEL": 0.02,
                "SYM_LOW_INTERFACE": 0.02,
                "SYM_HIGH_DEMISTER_DP": 0.02,
                "SYM_HIGH_VIBRATION": 0.02,
                "SYM_LOW_GAS_FLOW": 0.02,
                "SYM_HIGH_SCRUBBER_LEVEL": 0.02,
            },
        }

    def infer(self, evidence: Dict[str, int]) -> BayesianInferenceResult:
        """Compute posterior probabilities P(Fault | evidence) using exact Bayes rule."""
        posteriors: Dict[str, float] = {}
        marginal_evidence = 0.0

        for h in FAULT_STATES:
            prior = self.priors[h]
            # Likelihood product
            likelihood = 1.0
            for sym, val in evidence.items():
                if sym not in OBSERVABLE_SYMPTOMS:
                    continue
                p_sym_given_h = self.cpt[h][sym]
                # If observed present (val=1), use p; if observed absent (val=0), use (1 - p)
                prob_obs = p_sym_given_h if val == 1 else (1.0 - p_sym_given_h)
                likelihood *= prob_obs

            joint = prior * likelihood
            posteriors[h] = joint
            marginal_evidence += joint

        # Normalize posteriors
        if marginal_evidence > 0.0:
            for h in FAULT_STATES:
                posteriors[h] /= marginal_evidence
        else:
            # Fallback to priors if joint likelihood is zero
            posteriors = dict(self.priors)

        # Calculate Shannon Entropy: H = - sum(p * log2(p))
        entropy = 0.0
        for p in posteriors.values():
            if p > 1e-12:
                entropy -= p * math.log2(p)

        # Max entropy for 7 states is log2(7) ~ 2.807 bits
        max_entropy = math.log2(len(FAULT_STATES))
        norm_entropy = min(1.0, max(0.0, entropy / max_entropy))

        # Calculate Value of Information (Information Gain) for unobserved symptoms
        info_gains: Dict[str, float] = {}
        for sym in OBSERVABLE_SYMPTOMS:
            if sym in evidence:
                continue  # Already observed

            # Compute P(sym = 1 | current evidence)
            p_sym_1 = sum(posteriors[h] * self.cpt[h][sym] for h in FAULT_STATES)
            p_sym_0 = 1.0 - p_sym_1

            # Expected entropy if sym = 1
            h_1 = self._hypothetical_entropy(evidence, sym, 1)
            # Expected entropy if sym = 0
            h_0 = self._hypothetical_entropy(evidence, sym, 0)

            expected_posterior_entropy = p_sym_1 * h_1 + p_sym_0 * h_0
            gain = max(0.0, entropy - expected_posterior_entropy)
            info_gains[sym] = round(gain, 4)

        # Identify most informative next check
        best_check = max(info_gains.items(), key=lambda x: x[1])[0] if info_gains else None

        # Build ranked hypothesis belief objects
        ranked: List[HypothesisBelief] = []
        for h, post in sorted(posteriors.items(), key=lambda x: x[1], reverse=True):
            lr = (post / self.priors[h]) if self.priors[h] > 0 else 1.0
            ranked.append(
                HypothesisBelief(
                    hypothesis_id=h,
                    description=FAULT_DESCRIPTIONS.get(h, h),
                    posterior_prob=round(float(post), 4),
                    prior_prob=round(float(self.priors[h]), 4),
                    likelihood_ratio=round(float(lr), 2),
                )
            )

        return BayesianInferenceResult(
            ranked_hypotheses=ranked,
            shannon_entropy=round(float(entropy), 4),
            normalized_entropy=round(float(norm_entropy), 4),
            active_evidence=evidence,
            missing_evidence_gain=info_gains,
            most_informative_next_check=best_check,
        )

    def _hypothetical_entropy(self, current_evidence: Dict[str, int], new_sym: str, new_val: int) -> float:
        """Compute Shannon entropy under a hypothetical new observation."""
        hyp_evidence = dict(current_evidence)
        hyp_evidence[new_sym] = new_val

        posteriors = {}
        marginal = 0.0
        for h in FAULT_STATES:
            prior = self.priors[h]
            likelihood = 1.0
            for sym, val in hyp_evidence.items():
                if sym not in OBSERVABLE_SYMPTOMS:
                    continue
                p_cond = self.cpt[h][sym]
                prob_obs = p_cond if val == 1 else (1.0 - p_cond)
                likelihood *= prob_obs
            joint = prior * likelihood
            posteriors[h] = joint
            marginal += joint

        if marginal <= 0.0:
            return math.log2(len(FAULT_STATES))

        entropy = 0.0
        for joint in posteriors.values():
            p = joint / marginal
            if p > 1e-12:
                entropy -= p * math.log2(p)
        return entropy

    def to_pgmpy_model(self) -> Optional[Any]:
        """Convert domain parameters into a pgmpy DiscreteBayesianNetwork instance."""
        if not PGMPY_AVAILABLE:
            return None

        edges = [("Fault", sym) for sym in OBSERVABLE_SYMPTOMS]
        model = DiscreteBayesianNetwork(edges)

        # Fault Prior CPD
        fault_prior_vals = [[self.priors[h]] for h in FAULT_STATES]
        cpd_fault = TabularCPD(
            variable="Fault",
            variable_card=len(FAULT_STATES),
            values=fault_prior_vals,
            state_names={"Fault": FAULT_STATES},
        )
        model.add_cpds(cpd_fault)

        # Symptom CPDs (binary 0, 1) conditioned on Fault
        for sym in OBSERVABLE_SYMPTOMS:
            p_true = [self.cpt[h][sym] for h in FAULT_STATES]
            p_false = [1.0 - p for p in p_true]
            cpd_sym = TabularCPD(
                variable=sym,
                variable_card=2,
                values=[p_false, p_true],
                evidence=["Fault"],
                evidence_card=[len(FAULT_STATES)],
                state_names={sym: [0, 1], "Fault": FAULT_STATES},
            )
            model.add_cpds(cpd_sym)

        model.check_model()
        return model
