"""Content- and Graph-Based Action Recommender.

Ranks diagnostic checks and mitigating actions for operators subject to
hard safety eligibility rules, interlocks, and current operational constraints.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional, Set, Tuple
from src.reasoning.knowledge_graph import KnowledgeGraph


class RiskLevel(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


@dataclass
class ActionRecommendation:
    action_id: str
    name: str
    target_equipment: str
    score: float
    risk_level: RiskLevel
    eligible: bool
    blocking_reasons: List[str]
    rationale: str
    citations: List[str]


class SafetyEligibilityFilter:
    """Evaluates process interlocks and preconditions to ensure actions are safe to execute."""

    def __init__(self):
        pass

    def evaluate_eligibility(
        self, action_id: str, action_data: Dict[str, Any], plant_state: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """Check whether action satisfies operational preconditions and safety interlocks."""
        blocking_reasons: List[str] = []

        # Interlock 1: Manual bypass requires local operator presence or permit
        if action_id == "ACT_01_SWITCH_MANUAL_BYPASS":
            if not plant_state.get("permit_to_work", True):
                blocking_reasons.append("Permit to Work (PTW) not active for manual valve manipulation")
            if plant_state.get("pcv101_isolation_closed", False):
                blocking_reasons.append("Upstream isolation valve XV-101 is closed; bypass flow obstructed")

        # Interlock 2: Antifoam injection requires chemical tank inventory
        elif action_id == "ACT_02_INJECT_ANTIFOAM_CHEMICAL":
            chem_level = plant_state.get("antifoam_tank_level_pct", 50.0)
            if chem_level < 15.0:
                blocking_reasons.append(f"Antifoam storage tank inventory critical ({chem_level}% < 15%)")

        # Interlock 3: Anti-surge recycle requires cooler to be online to prevent overheating
        elif action_id == "ACT_03_OPEN_ANTISURGE_RECYCLE":
            if not plant_state.get("cooler_E101_online", True):
                blocking_reasons.append("Inter-stage gas cooler E-101 is offline; recycle will cause overtemperature trip")

        # Interlock 4: Bridle flushing requires closed drain header availability
        elif action_id == "ACT_04_FLUSH_INTERFACE_BRIDLE":
            if plant_state.get("closed_drain_high_pressure", False):
                blocking_reasons.append("Closed drain header backpressure too high for safe bridle depressurization")

        # Interlock 5: Divert to flare requires flare ignition verification
        elif action_id == "ACT_06_DIVERT_TO_FLARE":
            if not plant_state.get("flare_header_ignited", True):
                blocking_reasons.append("Flare pilot flame not confirmed ignited; venting unburnt hydrocarbons prohibited")

        is_eligible = len(blocking_reasons) == 0
        return is_eligible, blocking_reasons


class ContentGraphRecommender:
    """Ranks mitigating operational actions and diagnostic checks."""

    def __init__(self, knowledge_graph: Optional[KnowledgeGraph] = None):
        self.kg = knowledge_graph or KnowledgeGraph()
        self.safety_filter = SafetyEligibilityFilter()

        # Risk penalty weights
        self.risk_penalties = {
            RiskLevel.LOW: 0.05,
            RiskLevel.MEDIUM: 0.15,
            RiskLevel.HIGH: 0.35,
        }

    def recommend_actions(
        self,
        hypothesis_beliefs: Dict[str, float],
        plant_state: Optional[Dict[str, Any]] = None,
        top_k: int = 5,
    ) -> List[ActionRecommendation]:
        """Rank and filter corrective actions based on active hypothesis beliefs and safety rules."""
        plant_state = plant_state or {}
        candidate_actions: Dict[str, Dict[str, Any]] = {}
        action_hypo_support: Dict[str, float] = {}

        # Traverse Knowledge Graph from hypotheses to mitigations
        for hypo_id, belief in hypothesis_beliefs.items():
            if belief < 0.05:
                continue

            mitigations = self.kg.get_mitigations_for_hypothesis(hypo_id)
            for act in mitigations:
                act_id = act.get("id", "")
                if not act_id:
                    continue

                if act_id not in candidate_actions:
                    candidate_actions[act_id] = act
                    action_hypo_support[act_id] = 0.0

                action_hypo_support[act_id] += belief

        recommendations: List[ActionRecommendation] = []

        for act_id, act in candidate_actions.items():
            # Check safety eligibility
            is_eligible, blockers = self.safety_filter.evaluate_eligibility(act_id, act, plant_state)

            risk_str = act.get("risk_level", "Medium")
            try:
                risk_enum = RiskLevel(risk_str)
            except ValueError:
                risk_enum = RiskLevel.MEDIUM

            # Compute score: hypothesis belief support minus risk penalty
            support_score = action_hypo_support.get(act_id, 0.5)
            penalty = self.risk_penalties.get(risk_enum, 0.15)
            final_score = max(0.05, support_score - penalty)

            # Ineligible actions are severely penalized in rank but displayed with blockers
            if not is_eligible:
                final_score *= 0.10

            # Collect citations
            target_eq = act.get("target_equipment", "")
            citations = [f"SOP-{target_eq}"]

            rationale = (
                f"Addresses root causes with {support_score*100:.1f}% cumulative belief support. "
                f"Risk level: {risk_str}."
            )

            recommendations.append(
                ActionRecommendation(
                    action_id=act_id,
                    name=act.get("name", act_id),
                    target_equipment=target_eq,
                    score=round(final_score, 3),
                    risk_level=risk_enum,
                    eligible=is_eligible,
                    blocking_reasons=blockers,
                    rationale=rationale,
                    citations=citations,
                )
            )

        # Sort by score descending, putting eligible actions first
        recommendations.sort(key=lambda r: (r.eligible, r.score), reverse=True)
        return recommendations[:top_k]
