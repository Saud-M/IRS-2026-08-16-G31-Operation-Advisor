"""Forward Chaining Rule-Based Inference Engine.

Evaluates incoming real-time telemetry against operational boundaries
and composite domain rules to deduce active symptoms and candidate fault hypotheses.
Provides complete audit rule firing traces for verification and governance.
"""

from dataclasses import dataclass, field
import datetime
from typing import Dict, Any, List, Set, Optional, Callable


@dataclass
class RuleTrace:
    """Audit record of an executed rule."""
    rule_id: str
    rule_name: str
    antecedent: str
    consequent: str
    timestamp: str = field(default_factory=lambda: datetime.datetime.utcnow().isoformat())
    confidence: float = 1.0


@dataclass
class InferenceResult:
    """Output bundle from forward-chaining evaluation."""
    active_symptoms: List[str]
    candidate_hypotheses: List[str]
    rule_traces: List[RuleTrace]
    facts: Dict[str, Any]


class ForwardChainingEngine:
    """Forward-chaining inference engine executing declarative rules over process state."""

    def __init__(self):
        self.rules = self._init_rules()

    def _init_rules(self) -> List[Dict[str, Any]]:
        """Declare production rules (Antecedent Condition -> Consequent Fact)."""
        return [
            # Symptom Level Rules
            {
                "id": "R_SYM_01",
                "name": "Separator Overpressure Condition",
                "condition": lambda f: f.get("PT-101", 0.0) >= 34.0,
                "antecedent": "PT-101 >= 34.0 barg",
                "consequent_type": "symptom",
                "consequent": "SYM_HIGH_PRESSURE",
                "confidence": 0.95,
            },
            {
                "id": "R_SYM_02",
                "name": "Separator Underpressure Condition",
                "condition": lambda f: f.get("PT-101", 30.0) <= 26.0,
                "antecedent": "PT-101 <= 26.0 barg",
                "consequent_type": "symptom",
                "consequent": "SYM_LOW_PRESSURE",
                "confidence": 0.95,
            },
            {
                "id": "R_SYM_03",
                "name": "High Hydrocarbon Liquid Hold-Up",
                "condition": lambda f: f.get("LT-101", 50.0) >= 70.0,
                "antecedent": "LT-101 >= 70.0 %",
                "consequent_type": "symptom",
                "consequent": "SYM_HIGH_LEVEL",
                "confidence": 0.90,
            },
            {
                "id": "R_SYM_04",
                "name": "Low Water Interface Reading",
                "condition": lambda f: f.get("LT-102", 25.0) <= 15.0,
                "antecedent": "LT-102 <= 15.0 %",
                "consequent_type": "symptom",
                "consequent": "SYM_LOW_INTERFACE",
                "confidence": 0.85,
            },
            {
                "id": "R_SYM_05",
                "name": "Demister Pad Blinding Differential Pressure",
                "condition": lambda f: f.get("DP-101", f.get("DPIT-101", 0.10)) >= 0.45 or f.get("DPIT-101", 0.0) >= 0.45,
                "antecedent": "DPIT-101 >= 0.45 bar",
                "consequent_type": "symptom",
                "consequent": "SYM_HIGH_DEMISTER_DP",
                "confidence": 0.95,
            },
            {
                "id": "R_SYM_06",
                "name": "Centrifugal Compressor High Shaft Vibration",
                "condition": lambda f: f.get("VT-101", f.get("ST-101", 2.0)) >= 3.8 or f.get("ST-101", 2.0) >= 3.8,
                "antecedent": "VT-101 / ST-101 >= 3.8 mm/s",
                "consequent_type": "symptom",
                "consequent": "SYM_HIGH_VIBRATION",
                "confidence": 0.98,
            },
            {
                "id": "R_SYM_07",
                "name": "Restricted Gas Export Flow",
                "condition": lambda f: f.get("FT-101", 90000.0) <= 65000.0,
                "antecedent": "FT-101 <= 65000.0 Sm3/h",
                "consequent_type": "symptom",
                "consequent": "SYM_LOW_GAS_FLOW",
                "confidence": 0.90,
            },
            {
                "id": "R_SYM_08",
                "name": "Suction Scrubber Liquid High Accumulation",
                "condition": lambda f: f.get("LT-103", f.get("V102_scrubber_level", 5.0)) >= 10.0 or f.get("V102_scrubber_level", 5.0) >= 10.0,
                "antecedent": "LT-103 / V102_scrubber_level >= 10.0 %",
                "consequent_type": "symptom",
                "consequent": "SYM_HIGH_SCRUBBER_LEVEL",
                "confidence": 0.92,
            },
            # Composite Hypothesis Rules
            {
                "id": "R_HYPO_01",
                "name": "Deduce PCV-101 Stuck Closed",
                "condition": lambda f: "SYM_HIGH_PRESSURE" in f.get("_symptoms", set()) and (
                    "SYM_LOW_GAS_FLOW" in f.get("_symptoms", set()) or f.get("PCV-101_pos", 0.5) < 0.25
                ),
                "antecedent": "SYM_HIGH_PRESSURE AND (SYM_LOW_GAS_FLOW OR PCV-101_pos < 0.25)",
                "consequent_type": "hypothesis",
                "consequent": "H01",
                "confidence": 0.92,
            },
            {
                "id": "R_HYPO_02",
                "name": "Deduce PCV-101 Stuck Open",
                "condition": lambda f: "SYM_LOW_PRESSURE" in f.get("_symptoms", set()),
                "antecedent": "SYM_LOW_PRESSURE",
                "consequent_type": "hypothesis",
                "consequent": "H02",
                "confidence": 0.88,
            },
            {
                "id": "R_HYPO_03",
                "name": "Deduce Separator Foaming Carryover",
                "condition": lambda f: "SYM_HIGH_DEMISTER_DP" in f.get("_symptoms", set()) and (
                    "SYM_HIGH_SCRUBBER_LEVEL" in f.get("_symptoms", set()) or "SYM_HIGH_LEVEL" in f.get("_symptoms", set()) or f.get("DPIT-101", f.get("DP-101", 0.0)) >= 0.08
                ),
                "antecedent": "SYM_HIGH_DEMISTER_DP AND (SYM_HIGH_SCRUBBER_LEVEL OR SYM_HIGH_LEVEL)",
                "consequent_type": "hypothesis",
                "consequent": "H03",
                "confidence": 0.94,
            },
            {
                "id": "R_HYPO_04",
                "name": "Deduce Compressor K-101 Aerodynamic Surge",
                "condition": lambda f: "SYM_HIGH_VIBRATION" in f.get("_symptoms", set()) or (
                    f.get("VT-101", f.get("ST-101", 2.0)) >= 3.8 or f.get("surge_margin_pct", 30.0) <= 5.0
                ),
                "antecedent": "SYM_HIGH_VIBRATION OR surge_margin_pct <= 5.0%",
                "consequent_type": "hypothesis",
                "consequent": "H04",
                "confidence": 0.96,
            },
            {
                "id": "R_HYPO_05",
                "name": "Deduce Interface Emulsion Pad & Transmitter Drift",
                "condition": lambda f: "SYM_LOW_INTERFACE" in f.get("_symptoms", set()) and (
                    f.get("LT-101", 50.0) >= 45.0
                ),
                "antecedent": "SYM_LOW_INTERFACE AND LT-101 >= 45.0% (Oil hold-up normal/high)",
                "consequent_type": "hypothesis",
                "consequent": "H05",
                "confidence": 0.85,
            },
            {
                "id": "R_HYPO_06",
                "name": "Deduce Wellhead Transient Slug Influx",
                "condition": lambda f: "SYM_HIGH_LEVEL" in f.get("_symptoms", set()) and (
                    "SYM_HIGH_PRESSURE" in f.get("_symptoms", set())
                ),
                "antecedent": "SYM_HIGH_LEVEL AND SYM_HIGH_PRESSURE",
                "consequent_type": "hypothesis",
                "consequent": "H06",
                "confidence": 0.89,
            },
        ]

    def infer(self, facts: Dict[str, Any]) -> InferenceResult:
        """Execute exhaustive forward chaining until no new facts can be deduced."""
        working_facts = dict(facts)
        active_symptoms: Set[str] = set()
        candidate_hypotheses: Set[str] = set()
        traces: List[RuleTrace] = []

        fired_rule_ids: Set[str] = set()
        new_fact_added = True

        while new_fact_added:
            new_fact_added = False
            working_facts["_symptoms"] = active_symptoms

            for rule in self.rules:
                r_id = rule["id"]
                if r_id in fired_rule_ids:
                    continue

                try:
                    is_satisfied = rule["condition"](working_facts)
                except Exception:
                    is_satisfied = False

                if is_satisfied:
                    fired_rule_ids.add(r_id)
                    new_fact_added = True
                    consequent = rule["consequent"]
                    c_type = rule["consequent_type"]

                    if c_type == "symptom":
                        active_symptoms.add(consequent)
                    elif c_type == "hypothesis":
                        candidate_hypotheses.add(consequent)

                    traces.append(
                        RuleTrace(
                            rule_id=r_id,
                            rule_name=rule["name"],
                            antecedent=rule["antecedent"],
                            consequent=consequent,
                            confidence=rule["confidence"],
                        )
                    )

        # Default to nominal if no fault symptoms or hypotheses were deduced
        if not candidate_hypotheses and not active_symptoms:
            candidate_hypotheses.add("H07")

        return InferenceResult(
            active_symptoms=sorted(list(active_symptoms)),
            candidate_hypotheses=sorted(list(candidate_hypotheses)),
            rule_traces=traces,
            facts=facts,
        )
