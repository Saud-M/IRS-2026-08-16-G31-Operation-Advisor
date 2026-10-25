"""Bounded State-Space A* Search Planner with Dynamic Replanning.

Computes the minimal-cost, minimal-risk operational sequence from an abnormal
plant state to a verified safe operating state, and supports instant dynamic
replanning when an action is blocked or fails during execution.
"""

from dataclasses import dataclass, field
import heapq
from typing import Dict, Any, List, Optional, Set, Tuple


@dataclass(frozen=True)
class PlantPlanState:
    """Discrete operational state of the production facility."""
    pressure_status: str     # "NORMAL", "HIGH", "CRITICAL"
    liquid_status: str       # "NORMAL", "HIGH", "EMULSION"
    compressor_status: str   # "RUNNING", "SURGING", "SAFE_RECYCLE"
    pcv_status: str          # "AUTO", "MANUAL_BYPASS", "CLOSED_STUCK"
    antifoam_active: bool
    permit_granted: bool

    def is_goal(self) -> bool:
        """Goal condition: all process variables within normal or safe operating boundaries."""
        return (
            self.pressure_status == "NORMAL"
            and self.liquid_status == "NORMAL"
            and self.compressor_status in ("RUNNING", "SAFE_RECYCLE")
            and self.pcv_status in ("AUTO", "MANUAL_BYPASS", "BYPASS_DIVERTED")
        )

    def heuristic(self) -> float:
        """Admissible heuristic: count of unsatisfied safe operating conditions."""
        h = 0.0
        if self.pressure_status != "NORMAL":
            h += 2.0 if self.pressure_status == "CRITICAL" else 1.0
        if self.liquid_status != "NORMAL":
            h += 1.0
        if self.compressor_status not in ("RUNNING", "SAFE_RECYCLE"):
            h += 2.0
        if self.pcv_status not in ("AUTO", "MANUAL_BYPASS", "BYPASS_DIVERTED"):
            h += 2.0
        return h


@dataclass
class PlanStep:
    action_id: str
    name: str
    target_equipment: str
    estimated_time_min: float
    cost: float
    resulting_state: PlantPlanState


@dataclass
class PlanResult:
    is_feasible: bool
    total_cost: float
    estimated_duration_min: float
    steps: List[PlanStep]
    states_explored: int
    replanned: bool = False
    blocked_action_encountered: Optional[str] = None


class AStarPlanner:
    """A* search planner searching over discrete plant states and actions."""

    def __init__(self):
        self.blocked_actions: Set[str] = set()

    def set_blocked_action(self, action_id: str, blocked: bool = True) -> None:
        """Mark an action as blocked (e.g. valve mechanically seized in field)."""
        if blocked:
            self.blocked_actions.add(action_id)
        else:
            self.blocked_actions.discard(action_id)

    def get_valid_transitions(self, state: PlantPlanState) -> List[Tuple[str, str, str, float, float, PlantPlanState]]:
        """Return list of (action_id, name, target_equipment, duration_min, cost, next_state)."""
        transitions = []

        # 1. Obtain Permit to Work
        if not state.permit_granted and "REQ_PERMIT" not in self.blocked_actions:
            transitions.append((
                "REQ_PERMIT",
                "Obtain Emergency Hot Work / Isolation Permit",
                "Control_Room",
                4.0,
                4.0,
                PlantPlanState(
                    pressure_status=state.pressure_status,
                    liquid_status=state.liquid_status,
                    compressor_status=state.compressor_status,
                    pcv_status=state.pcv_status,
                    antifoam_active=state.antifoam_active,
                    permit_granted=True,
                ),
            ))

        # 2. Switch PCV-101 to Manual Station / Crack Open Bypass
        if (
            state.pcv_status == "CLOSED_STUCK"
            and state.permit_granted
            and "ACT_01_SWITCH_MANUAL_BYPASS" not in self.blocked_actions
        ):
            transitions.append((
                "ACT_01_SWITCH_MANUAL_BYPASS",
                "Switch PCV-101 to Manual Bypass Valve",
                "PCV-101",
                5.0,
                5.0,
                PlantPlanState(
                    pressure_status="NORMAL",
                    liquid_status=state.liquid_status,
                    compressor_status=state.compressor_status,
                    pcv_status="MANUAL_BYPASS",
                    antifoam_active=state.antifoam_active,
                    permit_granted=state.permit_granted,
                ),
            ))

        # 3. Start Antifoam Chemical Injection
        if (
            state.liquid_status == "HIGH"
            and not state.antifoam_active
            and "ACT_02_INJECT_ANTIFOAM_CHEMICAL" not in self.blocked_actions
        ):
            transitions.append((
                "ACT_02_INJECT_ANTIFOAM_CHEMICAL",
                "Start Antifoam Dosing Pump P-105",
                "V-101",
                3.0,
                3.0,
                PlantPlanState(
                    pressure_status=state.pressure_status,
                    liquid_status="NORMAL",
                    compressor_status=state.compressor_status,
                    pcv_status=state.pcv_status,
                    antifoam_active=True,
                    permit_granted=state.permit_granted,
                ),
            ))

        # 4. Trigger Anti-Surge Valve Fast-Open
        if (
            state.compressor_status == "SURGING"
            and "ACT_03_OPEN_ANTISURGE_RECYCLE" not in self.blocked_actions
        ):
            transitions.append((
                "ACT_03_OPEN_ANTISURGE_RECYCLE",
                "Trigger Fast-Opening of Anti-Surge Recycle Valve ASV-101",
                "K-101",
                2.0,
                2.5,
                PlantPlanState(
                    pressure_status=state.pressure_status,
                    liquid_status=state.liquid_status,
                    compressor_status="SAFE_RECYCLE",
                    pcv_status=state.pcv_status,
                    antifoam_active=state.antifoam_active,
                    permit_granted=state.permit_granted,
                ),
            ))

        # 5. Flush Interface Level Bridle (Emulsion Clearing)
        if (
            state.liquid_status == "EMULSION"
            and state.permit_granted
            and "ACT_04_FLUSH_INTERFACE_BRIDLE" not in self.blocked_actions
        ):
            transitions.append((
                "ACT_04_FLUSH_INTERFACE_BRIDLE",
                "Isolate and Flush LT-102 External Level Bridle",
                "LT-102",
                8.0,
                8.0,
                PlantPlanState(
                    pressure_status=state.pressure_status,
                    liquid_status="NORMAL",
                    compressor_status=state.compressor_status,
                    pcv_status=state.pcv_status,
                    antifoam_active=state.antifoam_active,
                    permit_granted=state.permit_granted,
                ),
            ))

        # 6. Pinch Upstream Production Choke (Pressure Mitigation without Bypass)
        if (
            state.pressure_status in ("HIGH", "CRITICAL")
            and "ACT_05_PINCH_WELLHEAD_CHOKE" not in self.blocked_actions
        ):
            transitions.append((
                "ACT_05_PINCH_WELLHEAD_CHOKE",
                "Throttle Upstream Choke Manifold by 15%",
                "Wellhead_Choke",
                6.0,
                7.0,
                PlantPlanState(
                    pressure_status="NORMAL",
                    liquid_status=state.liquid_status,
                    compressor_status=state.compressor_status,
                    pcv_status=state.pcv_status,
                    antifoam_active=state.antifoam_active,
                    permit_granted=state.permit_granted,
                ),
            ))

        # 7. Divert to High-Pressure Flare Header (Higher Risk Fallback)
        if (
            state.pressure_status in ("HIGH", "CRITICAL")
            and "ACT_06_DIVERT_TO_FLARE" not in self.blocked_actions
        ):
            transitions.append((
                "ACT_06_DIVERT_TO_FLARE",
                "Crack Open High-Pressure Relief Flare Valve BDV-101",
                "V-101",
                1.5,
                12.0,  # High risk penalty
                PlantPlanState(
                    pressure_status="NORMAL",
                    liquid_status=state.liquid_status,
                    compressor_status=state.compressor_status,
                    pcv_status="BYPASS_DIVERTED",
                    antifoam_active=state.antifoam_active,
                    permit_granted=state.permit_granted,
                ),
            ))

        return transitions

    def plan(self, initial_state: PlantPlanState) -> PlanResult:
        """Run A* search algorithm to discover minimal-cost response plan."""
        # Priority queue item: (f_score, counter, g_score, current_state, path)
        counter = 0
        open_set = []
        g_scores: Dict[PlantPlanState, float] = {initial_state: 0.0}

        heapq.heappush(open_set, (initial_state.heuristic(), counter, 0.0, initial_state, []))
        explored_count = 0

        while open_set:
            f_curr, _, g_curr, current_state, path = heapq.heappop(open_set)
            explored_count += 1

            if current_state.is_goal():
                total_duration = sum(step.estimated_time_min for step in path)
                return PlanResult(
                    is_feasible=True,
                    total_cost=round(g_curr, 2),
                    estimated_duration_min=round(total_duration, 1),
                    steps=path,
                    states_explored=explored_count,
                    replanned=bool(self.blocked_actions),
                )

            for act_id, act_name, target_eq, duration, cost, next_state in self.get_valid_transitions(current_state):
                tentative_g = g_curr + cost

                if next_state not in g_scores or tentative_g < g_scores[next_state]:
                    g_scores[next_state] = tentative_g
                    f_score = tentative_g + next_state.heuristic()
                    counter += 1

                    new_step = PlanStep(
                        action_id=act_id,
                        name=act_name,
                        target_equipment=target_eq,
                        estimated_time_min=duration,
                        cost=cost,
                        resulting_state=next_state,
                    )
                    heapq.heappush(open_set, (f_score, counter, tentative_g, next_state, path + [new_step]))

        return PlanResult(
            is_feasible=False,
            total_cost=float("inf"),
            estimated_duration_min=0.0,
            steps=[],
            states_explored=explored_count,
            replanned=bool(self.blocked_actions),
        )

    def replan_with_blocked_node(self, initial_state: PlantPlanState, failed_action_id: str) -> PlanResult:
        """Trigger dynamic replan when an action is reported blocked or failed by operator."""
        self.set_blocked_action(failed_action_id, blocked=True)
        result = self.plan(initial_state)
        result.blocked_action_encountered = failed_action_id
        return result
