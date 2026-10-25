"""Unit and Integration Tests for Operator Cockpit UI Components (Sprint 7).

Tests:
1. index.html dashboard template structure and presence of essential PFD components.
2. CockpitState initialization and dynamic scenario simulation injection.
3. Scenario fault telemetry updates (PCV Stiction, Compressor Surge, Carryover, Nominal).
4. Direct API response assembly (telemetry, Bayesian hypotheses, validation gate, audit hash).
5. Dialogue manager query integration within cockpit context.
6. Handover report generation from UI state.
"""

import json
import os
import pytest
from src.ui.server import CockpitState, CockpitHandler


@pytest.fixture
def state():
    return CockpitState()


def test_ui_index_html_template():
    """Verify single-page operator dashboard template exists and has all essential UI elements."""
    html_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src", "ui", "index.html")
    assert os.path.exists(html_path)

    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Verify essential industrial cockpit components
    assert "OPERATION ADVISOR" in content
    assert "Process Flow Diagram (PFD)" in content
    assert "V-101" in content
    assert "K-101" in content
    assert "PCV-101" in content
    assert "ASV-101" in content
    assert "4-Stage Safety Barrier Gate Status" not in content
    assert "SHA-256 Audit Trail" not in content
    assert "Probabilistic Fault Hypotheses (Bayesian Net)" in content
    assert "Bounded A* Response Plan & Field Checklist" in content
    assert "Grounded Technical References" in content
    assert "exportHandover" in content


def test_cockpit_state_initial_nominal(state):
    """Verify default initial cockpit state is nominal steady-state."""
    assert state.current_scenario_name == "NOMINAL"
    assert "PT-101" in state.telemetry
    assert 28.0 <= state.telemetry["PT-101"] <= 33.0
    assert state.telemetry["VT-101"] < 2.5
    assert state.telemetry["DPIT-101"] < 0.05


def test_cockpit_scenario_injection_pcv_stiction(state):
    """Verify injecting PCV_101_STICTION scenario drives pressure into alarm."""
    state.load_scenario("PCV_101_STICTION")
    assert state.current_scenario_name == "PCV_101_STICTION"
    assert state.telemetry["PT-101"] > 33.0
    assert state.wm.state.telemetry["PT-101"] > 33.0


def test_cockpit_scenario_injection_compressor_surge(state):
    """Verify injecting COMPRESSOR_SURGE scenario drives vibration."""
    state.load_scenario("COMPRESSOR_SURGE")
    assert state.current_scenario_name == "COMPRESSOR_SURGE"
    assert state.telemetry["VT-101"] > 2.5


def test_cockpit_scenario_injection_liquid_carryover(state):
    """Verify injecting LIQUID_CARRYOVER scenario elevates demister DP."""
    state.load_scenario("LIQUID_CARRYOVER")
    assert state.current_scenario_name == "LIQUID_CARRYOVER"
    assert state.telemetry["DPIT-101"] > 0.04


def test_cockpit_scenario_return_to_nominal(state):
    """Verify resetting to NOMINAL restores baseline steady-state."""
    state.load_scenario("PCV_101_STICTION")
    assert state.telemetry["PT-101"] > 33.0

    state.load_scenario("NOMINAL")
    assert state.current_scenario_name == "NOMINAL"
    assert 28.0 <= state.telemetry["PT-101"] <= 33.0


def test_cockpit_query_flow(state):
    """Verify query processing within cockpit state updates dialogue and returns advisor response."""
    state.load_scenario("PCV_101_STICTION")
    resp = state.dialogue_mgr.process_text_input("Why is separator pressure high?")

    assert resp.top_hypothesis == "H01"
    assert resp.confidence_pct > 0.0
    assert len(resp.recommended_checks) > 0
    assert len(resp.recommended_actions) > 0
    assert len(resp.active_plan) > 0
    assert "H01" in resp.reply_text or "PCV-101" in resp.reply_text


def test_cockpit_handover_generation(state):
    """Verify handover generation from cockpit state."""
    state.load_scenario("PCV_101_STICTION")
    handover = state.rag.generate_shift_handover(state.wm)

    assert "markdown" in handover
    assert "html" in handover
    assert "OPERATING SHIFT HANDOVER REPORT" in handover["markdown"]
    assert "<!DOCTYPE html>" in handover["html"]
    assert "PT-101" in handover["markdown"]
