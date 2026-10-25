"""Rule and Logical Constraint Consistency Validator.

Detects contradictory machine reasoning outputs:
1. Mutually exclusive fault hypotheses (e.g., PCV-101 Stuck Closed vs PCV-101 Stuck Open).
2. Polar opposite operational symptoms (e.g., High Pressure vs Low Pressure).
3. Nominal state conflict (asserting Nominal Steady-State while abnormal alarms are active).
"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple, Set


@dataclass
class ConsistencyIssue:
    check_name: str
    severity: str        # "CRITICAL", "WARNING"
    conflicting_elements: List[str]
    message: str


class RuleConsistencyValidator:
    """Enforces non-contradictory logical deductions across reasoning engines."""

    # Pairs of mutually exclusive hypotheses that cannot both be asserted
    MUTUALLY_EXCLUSIVE_HYPOTHESES = [
        ({"H01", "H02"}, "PCV-101 cannot be simultaneously Stuck Closed (H01) and Stuck Open (H02)."),
        ({"H01", "H07"}, "Cannot assert Nominal Steady-State (H07) while PCV-101 Stuck Closed (H01) is active."),
        ({"H02", "H07"}, "Cannot assert Nominal Steady-State (H07) while PCV-101 Stuck Open (H02) is active."),
        ({"H03", "H07"}, "Cannot assert Nominal Steady-State (H07) while Foaming/Carryover (H03) is active."),
        ({"H04", "H07"}, "Cannot assert Nominal Steady-State (H07) while Compressor Surge (H04) is active."),
        ({"H05", "H07"}, "Cannot assert Nominal Steady-State (H07) while Emulsion Rag Layer (H05) is active."),
        ({"H06", "H07"}, "Cannot assert Nominal Steady-State (H07) while Severe Slug Influx (H06) is active."),
    ]

    # Pairs of polar opposite symptoms
    MUTUALLY_EXCLUSIVE_SYMPTOMS = [
        ({"SYM_HIGH_PRESSURE", "SYM_LOW_PRESSURE"}, "Separator cannot exhibit High Pressure and Low Pressure simultaneously."),
        ({"SYM_HIGH_LEVEL", "SYM_LOW_LEVEL"}, "Vessel cannot exhibit High Liquid Level and Low Liquid Level simultaneously."),
    ]

    def validate_symptoms(self, active_symptoms: Set[str]) -> Tuple[bool, List[ConsistencyIssue]]:
        """Verify that active symptoms contain no logical polar contradictions."""
        issues: List[ConsistencyIssue] = []

        for mutex_set, explanation in self.MUTUALLY_EXCLUSIVE_SYMPTOMS:
            if mutex_set.issubset(active_symptoms):
                issues.append(
                    ConsistencyIssue(
                        check_name="CONTRADICTORY_SYMPTOMS_ASSERTION",
                        severity="CRITICAL",
                        conflicting_elements=sorted(list(mutex_set)),
                        message=f"Logical Contradiction: {explanation}",
                    )
                )

        is_valid = len(issues) == 0
        return is_valid, issues

    def validate_hypothesis_rankings(
        self,
        beliefs: Dict[str, float],
        belief_threshold: float = 0.35,
    ) -> Tuple[bool, List[ConsistencyIssue]]:
        """Verify that high-belief diagnoses do not contain mutually exclusive fault pairs."""
        issues: List[ConsistencyIssue] = []
        high_belief_hypotheses = {h for h, prob in beliefs.items() if prob >= belief_threshold}

        for mutex_set, explanation in self.MUTUALLY_EXCLUSIVE_HYPOTHESES:
            if mutex_set.issubset(high_belief_hypotheses):
                probs = {h: beliefs[h] for h in mutex_set}
                issues.append(
                    ConsistencyIssue(
                        check_name="CONTRADICTORY_HYPOTHESIS_PAIR",
                        severity="CRITICAL",
                        conflicting_elements=sorted(list(mutex_set)),
                        message=f"Diagnostic Contradiction: {explanation} Conflicting beliefs: {probs}",
                    )
                )

        is_valid = len(issues) == 0
        return is_valid, issues
