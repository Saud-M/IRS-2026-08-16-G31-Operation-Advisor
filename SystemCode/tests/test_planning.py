"""Unit and Integration Tests for Planning & Optimization Module (Sprint 4).
Verifies A* response plan synthesis, dynamic replanning on blocked actions, and GA setpoint optimization.
"""

import pytest
from src.planning.astar_planner import AStarPlanner, PlantPlanState
from src.planning.ga_optimizer import GeneticAlgorithmOptimizer


def test_astar_planner_goal_reached_immediately():
    """Verify that an already safe state requires zero transitions."""
    planner = AStarPlanner()
    safe_state = PlantPlanState(
        pressure_status="NORMAL",
        liquid_status="NORMAL",
        compressor_status="RUNNING",
        pcv_status="AUTO",
        antifoam_active=False,
        permit_granted=True,
    )
    result = planner.plan(safe_state)
    assert result.is_feasible is True
    assert len(result.steps) == 0
    assert result.total_cost == 0.0


def test_astar_planning_overpressure_sequence():
    """Verify optimal 2-step plan: Obtain Permit -> Switch Manual Bypass."""
    planner = AStarPlanner()
    abnormal_state = PlantPlanState(
        pressure_status="HIGH",
        liquid_status="NORMAL",
        compressor_status="RUNNING",
        pcv_status="CLOSED_STUCK",
        antifoam_active=False,
        permit_granted=False,
    )

    result = planner.plan(abnormal_state)
    assert result.is_feasible is True
    assert len(result.steps) == 2
    step_ids = [step.action_id for step in result.steps]
    assert step_ids == ["REQ_PERMIT", "ACT_01_SWITCH_MANUAL_BYPASS"]
    # Final state should be safe
    assert result.steps[-1].resulting_state.is_goal() is True


def test_astar_dynamic_replanning_on_blocked_action():
    """Verify dynamic replanning when bypass valve is blocked/seized in field."""
    planner = AStarPlanner()
    abnormal_state = PlantPlanState(
        pressure_status="HIGH",
        liquid_status="NORMAL",
        compressor_status="RUNNING",
        pcv_status="CLOSED_STUCK",
        antifoam_active=False,
        permit_granted=False,
    )

    # Initial plan uses bypass
    initial_plan = planner.plan(abnormal_state)
    assert initial_plan.steps[-1].action_id == "ACT_01_SWITCH_MANUAL_BYPASS"

    # Operator notifies: manual bypass seized! Trigger dynamic replan
    replanned_res = planner.replan_with_blocked_node(abnormal_state, "ACT_01_SWITCH_MANUAL_BYPASS")
    assert replanned_res.is_feasible is True
    assert replanned_res.replanned is True
    assert replanned_res.blocked_action_encountered == "ACT_01_SWITCH_MANUAL_BYPASS"

    # Replanned path must not use the blocked bypass action
    replan_step_ids = [step.action_id for step in replanned_res.steps]
    assert "ACT_01_SWITCH_MANUAL_BYPASS" not in replan_step_ids
    # Should use relief flare instead
    assert "ACT_06_DIVERT_TO_FLARE" in replan_step_ids
    assert replanned_res.steps[-1].resulting_state.is_goal() is True


def test_genetic_algorithm_optimizer():
    """Verify that GA evolves setpoints within bounds and achieves objective improvement."""
    optimizer = GeneticAlgorithmOptimizer(
        population_size=30,
        generations=25,
        random_seed=42,
    )
    res = optimizer.optimize()

    assert res.best_fitness > res.baseline_fitness
    assert res.improvement_pct > 3.0
    assert len(res.fitness_history) == 25

    # Check bounds
    sp = res.best_setpoints
    assert 27.5 <= sp.separator_pressure_barg <= 33.0
    assert 16.0 <= sp.anti_surge_margin_pct <= 35.0
    assert 45.0 <= sp.liquid_level_pct <= 55.0
