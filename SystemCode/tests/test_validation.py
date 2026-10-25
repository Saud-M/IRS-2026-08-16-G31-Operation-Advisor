"""Unit and Integration Tests for Validation Pipeline & Safety Barriers (Sprint 7).

Verifies:
1. Dimensional & thermodynamic unit checks (conservation laws, envelope bounds).
2. Interface level <= total liquid level physical enforcement.
3. Telemetry freshness, latency thresholds, and flatline frozen sensor detection.
4. Rule & logical contradiction prevention (mutually exclusive hypotheses/symptoms).
5. Safety barrier: Read-only boundary (no direct DCS writes) and spurious flaring interlocks.
6. Cryptographic SHA-256 audit trail chaining and integrity verification.
7. End-to-end multi-stage validation pipeline execution.
"""

from datetime import datetime, timedelta, timezone
import json
import os
import pytest

from src.validation.unit_validator import UnitConsistencyValidator
from src.validation.freshness_checker import TelemetryFreshnessChecker
from src.validation.rule_consistency import RuleConsistencyValidator
from src.validation.safety_barrier import SafetyBarrierValidator
from src.validation.audit_logger import AuditTrailLogger
from src.validation.pipeline import ValidationPipeline


@pytest.fixture
def unit_val():
    return UnitConsistencyValidator()


@pytest.fixture
def fresh_check():
    return TelemetryFreshnessChecker(history_len=4)


@pytest.fixture
def rule_val():
    return RuleConsistencyValidator()


@pytest.fixture
def barrier_val():
    return SafetyBarrierValidator()


@pytest.fixture
def pipeline(tmp_path):
    log_file = tmp_path / "test_audit.jsonl"
    return ValidationPipeline(log_path=str(log_file))


def test_unit_consistency_valid_telemetry(unit_val):
    """Verify nominal process readings pass thermodynamic envelope checks."""
    nominal = {
        "PT-101": 31.2,
        "PT-102": 30.5,
        "PT-103": 75.0,
        "LT-101": 50.0,
        "LT-102": 48.0,
        "DPIT-101": 0.025,
        "VT-101": 1.2,
    }
    is_valid, issues = unit_val.validate_snapshot(nominal)
    assert is_valid is True
    assert len(issues) == 0


def test_unit_consistency_out_of_bounds(unit_val):
    """Verify negative pressure triggers critical physical violation."""
    invalid = {"PT-101": -5.0, "LT-101": 50.0}
    is_valid, issues = unit_val.validate_snapshot(invalid)
    assert is_valid is False
    assert any(iss.check_name == "LOWER_PHYSICAL_BOUND_VIOLATION" for iss in issues)


def test_interface_exceeds_total_level_violation(unit_val):
    """Verify physical law violation: interface level cannot exceed total level."""
    inversion = {
        "LT-101": 40.0,
        "LT-102": 65.0,  # 65% interface > 40% total is physically impossible
    }
    is_valid, issues = unit_val.validate_snapshot(inversion)
    assert is_valid is False
    assert any(iss.check_name == "INTERFACE_TOTAL_LEVEL_INVERSION" for iss in issues)


def test_compressor_reverse_pressure_ratio(unit_val):
    """Verify thermodynamic violation: compressor discharge must exceed suction."""
    reversed_p = {
        "PT-102": 30.0,  # Suction
        "PT-103": 20.0,  # Discharge lower than suction!
    }
    is_valid, issues = unit_val.validate_snapshot(reversed_p)
    assert is_valid is False
    assert any(iss.check_name == "COMPRESSOR_REVERSE_PRESSURE_RATIO" for iss in issues)


def test_telemetry_freshness_latency(fresh_check):
    """Verify stale telemetry (> 30s latency) suspends advisory engine."""
    now = datetime.now(timezone.utc)
    stale_sample = now - timedelta(seconds=45)

    is_valid, issues = fresh_check.check_freshness(
        telemetry={"PT-101": 31.0},
        sample_timestamp=stale_sample,
        current_time=now,
    )
    assert is_valid is False
    assert any(iss.check_name == "STALE_TELEMETRY_DATA" for iss in issues)


def test_telemetry_flatline_detection(fresh_check):
    """Verify frozen sensor flatline across consecutive polling cycles."""
    # Feed identical values
    issues = []
    for _ in range(4):
        _, iss = fresh_check.check_freshness(telemetry={"PT-101": 31.0})
        issues.extend(iss)

    assert any(i.check_name == "FROZEN_SENSOR_FLATLINE" for i in issues)


def test_rule_consistency_mutually_exclusive_hypotheses(rule_val):
    """Verify contradictory hypotheses (H01 Stuck Closed & H02 Stuck Open) are flagged."""
    contradictory_beliefs = {
        "H01": 0.60,
        "H02": 0.55,
    }
    is_valid, issues = rule_val.validate_hypothesis_rankings(contradictory_beliefs)
    assert is_valid is False
    assert any(i.check_name == "CONTRADICTORY_HYPOTHESIS_PAIR" for i in issues)


def test_safety_barrier_prohibited_direct_dcs_write(barrier_val):
    """Verify system blocks any automated write command to DCS."""
    forbidden_plan = [
        {"action_id": "WRITE_DCS_CONTROLLER_SP", "target_equipment": "PCV-101"}
    ]
    is_valid, violations = barrier_val.validate_action_plan(forbidden_plan, telemetry={"PT-101": 35.0})
    assert is_valid is False
    assert any(v.check_name == "PROHIBITED_AUTOMATED_WRITE_COMMAND" for v in violations)


def test_safety_barrier_spurious_flaring_prevention(barrier_val):
    """Verify emergency flaring BDV-101 is blocked during normal separator pressure."""
    normal_p_flaring = [
        {"action_id": "ACT_06_DIVERT_TO_FLARE", "target_equipment": "V-101"}
    ]
    is_valid, violations = barrier_val.validate_action_plan(normal_p_flaring, telemetry={"PT-101": 31.0})
    assert is_valid is False
    assert any(v.check_name == "SPURIOUS_FLARING_INTERLOCK_VIOLATION" for v in violations)


def test_audit_logger_hash_chain_integrity(tmp_path):
    """Verify cryptographic SHA-256 hash chaining and tamper detection in audit logs."""
    log_file = tmp_path / "chain_audit.jsonl"
    logger = AuditTrailLogger(log_path=str(log_file))

    # Log 3 events
    rec1 = logger.log_session(
        session_id="S1", incident_id="INC-1", telemetry={"PT-101": 31.0},
        active_symptoms=[], top_hypothesis="H07", confidence_pct=95.0,
        recommended_actions=[], cited_documents=["[SOP-V101]"],
        validation_status="PASSED", validation_issues=[]
    )
    rec2 = logger.log_session(
        session_id="S2", incident_id="INC-1", telemetry={"PT-101": 35.5},
        active_symptoms=["SYM_HIGH_PRESSURE"], top_hypothesis="H01", confidence_pct=65.0,
        recommended_actions=["ACT_01_SWITCH_MANUAL_BYPASS"], cited_documents=["[SOP-V101 Section 1]"],
        validation_status="PASSED", validation_issues=[]
    )

    valid, count = logger.verify_chain_integrity()
    assert valid is True
    assert count == 2

    # Tamper with record 1 in the file
    with open(str(log_file), "r", encoding="utf-8") as f:
        lines = f.readlines()
    data = json.loads(lines[0])
    data["confidence_pct"] = 99.99  # Tampered!
    lines[0] = json.dumps(data) + "\n"
    with open(str(log_file), "w", encoding="utf-8") as f:
        f.writelines(lines)

    # Re-verify should detect tampering
    valid_after_tamper, error_line = logger.verify_chain_integrity()
    assert valid_after_tamper is False
    assert error_line == 1


def test_validation_pipeline_end_to_end(pipeline):
    """Verify full validation pipeline across multiple stages and audit recording."""
    nominal_telemetry = {"PT-101": 31.0, "LT-101": 50.0, "LT-102": 45.0, "DPIT-101": 0.02, "VT-101": 1.2}
    report = pipeline.validate_cycle(
        telemetry=nominal_telemetry,
        active_symptoms=set(),
        hypothesis_beliefs={"H07": 0.95},
        candidate_plan=[],
        incident_id="INC-TEST-01",
        top_hypothesis="H07",
        confidence_pct=95.0,
    )
    assert report.is_valid is True
    assert report.status == "PASSED"
    assert report.risk_score == 0.0
    assert report.audit_record_hash is not None

    # Test rejection when physical limit breached
    breached_telemetry = {"PT-101": -2.0, "LT-101": 30.0, "LT-102": 50.0}
    bad_report = pipeline.validate_cycle(
        telemetry=breached_telemetry,
        active_symptoms=set(),
        hypothesis_beliefs={},
        candidate_plan=[],
    )
    assert bad_report.is_valid is False
    assert bad_report.status == "REJECTED"
    assert len(bad_report.critical_messages) >= 2
