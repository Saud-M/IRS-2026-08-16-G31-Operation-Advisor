"""End-to-End Safety and Validation Pipeline for Operation Advisor.

Executes a sequential 4-stage validation gate:
1. Stage 1: Dimensional & Thermodynamic Unit Consistency
2. Stage 2: Data Freshness & Sensor Quality (Flatline / Spike / Latency)
3. Stage 3: Rule & Reasoning Constraint Consistency (Contradiction Checks)
4. Stage 4: Safety Barrier & Human-in-the-Loop Interlock Verification
Followed by tamper-evident Audit Logging in JSONL.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Set
import uuid

from src.validation.unit_validator import UnitConsistencyValidator, ValidationIssue
from src.validation.freshness_checker import TelemetryFreshnessChecker, FreshnessIssue
from src.validation.rule_consistency import RuleConsistencyValidator, ConsistencyIssue
from src.validation.safety_barrier import SafetyBarrierValidator, SafetyViolation
from src.validation.audit_logger import AuditTrailLogger, AuditRecord


@dataclass
class ValidationReport:
    session_id: str
    is_valid: bool
    status: str                         # "PASSED", "WARNING", "REJECTED"
    unit_issues: List[ValidationIssue] = field(default_factory=list)
    freshness_issues: List[FreshnessIssue] = field(default_factory=list)
    consistency_issues: List[ConsistencyIssue] = field(default_factory=list)
    safety_violations: List[SafetyViolation] = field(default_factory=list)
    critical_messages: List[str] = field(default_factory=list)
    warning_messages: List[str] = field(default_factory=list)
    risk_score: float = 0.0             # [0.0 = fully safe, 1.0 = hazardous rejection]
    audit_record_hash: Optional[str] = None


class ValidationPipeline:
    """Integrated safety gate evaluating incoming telemetry, reasoning outputs, and candidate plans."""

    def __init__(self, log_path: Optional[str] = None):
        self.unit_val = UnitConsistencyValidator()
        self.fresh_check = TelemetryFreshnessChecker()
        self.rule_val = RuleConsistencyValidator()
        self.barrier_val = SafetyBarrierValidator()
        self.audit_logger = AuditTrailLogger(log_path=log_path)

    def validate_cycle(
        self,
        telemetry: Dict[str, Any],
        active_symptoms: Optional[Set[str]] = None,
        hypothesis_beliefs: Optional[Dict[str, float]] = None,
        candidate_plan: Optional[List[Dict[str, Any]]] = None,
        sample_timestamp: Optional[datetime] = None,
        current_time: Optional[datetime] = None,
        permit_to_work_granted: bool = True,
        incident_id: str = "INC-UNKNOWN",
        top_hypothesis: Optional[str] = None,
        confidence_pct: float = 0.0,
        cited_documents: Optional[List[str]] = None,
        operator_feedback: Optional[str] = None,
    ) -> ValidationReport:
        """Execute full 4-stage validation barrier before presenting advice to human operators."""
        session_id = f"VAL-{uuid.uuid4().hex[:8].upper()}"
        critical_msgs: List[str] = []
        warning_msgs: List[str] = []

        # Stage 1: Dimensional & Thermodynamic Consistency
        unit_ok, unit_issues = self.unit_val.validate_snapshot(telemetry)
        for iss in unit_issues:
            if iss.severity == "CRITICAL":
                critical_msgs.append(f"[Unit Violation] {iss.message}")
            else:
                warning_msgs.append(f"[Unit Warning] {iss.message}")

        # Stage 2: Telemetry Freshness & Signal Stability
        fresh_ok, fresh_issues = self.fresh_check.check_freshness(
            telemetry=telemetry,
            sample_timestamp=sample_timestamp,
            current_time=current_time,
        )
        for iss in fresh_issues:
            if iss.severity == "CRITICAL":
                critical_msgs.append(f"[Freshness Violation] {iss.message}")
            else:
                warning_msgs.append(f"[Freshness Warning] {iss.message}")

        # Stage 3: Rule & Contradiction Consistency
        consistency_issues: List[ConsistencyIssue] = []
        if active_symptoms:
            sym_ok, sym_issues = self.rule_val.validate_symptoms(active_symptoms)
            consistency_issues.extend(sym_issues)
            for iss in sym_issues:
                if iss.severity == "CRITICAL":
                    critical_msgs.append(f"[Rule Contradiction] {iss.message}")
                else:
                    warning_msgs.append(f"[Rule Warning] {iss.message}")

        if hypothesis_beliefs:
            hyp_ok, hyp_issues = self.rule_val.validate_hypothesis_rankings(hypothesis_beliefs)
            consistency_issues.extend(hyp_issues)
            for iss in hyp_issues:
                if iss.severity == "CRITICAL":
                    critical_msgs.append(f"[Hypothesis Contradiction] {iss.message}")
                else:
                    warning_msgs.append(f"[Hypothesis Warning] {iss.message}")

        # Stage 4: Safety Barrier & Plan Interlocks
        safety_violations: List[SafetyViolation] = []
        if candidate_plan:
            plan_ok, p_violations = self.barrier_val.validate_action_plan(
                plan_steps=candidate_plan,
                telemetry=telemetry,
                permit_to_work_granted=permit_to_work_granted,
            )
            safety_violations.extend(p_violations)
            for v in p_violations:
                if v.severity == "CRITICAL":
                    critical_msgs.append(f"[Safety Barrier Violation] {v.message}")
                else:
                    warning_msgs.append(f"[Safety Warning] {v.message}")

        # Determine Composite Gate Status
        if critical_msgs:
            status = "REJECTED"
            is_valid = False
            risk_score = min(1.0, 0.6 + len(critical_msgs) * 0.15)
        elif warning_msgs:
            status = "WARNING"
            is_valid = True
            risk_score = min(0.5, len(warning_msgs) * 0.1)
        else:
            status = "PASSED"
            is_valid = True
            risk_score = 0.0

        # Stage 5: Immutable Cryptographic Audit Logging
        rec_actions = [p.get("action_id", "ACT") for p in candidate_plan] if candidate_plan else []
        audit_rec = self.audit_logger.log_session(
            session_id=session_id,
            incident_id=incident_id,
            telemetry=telemetry,
            active_symptoms=list(active_symptoms) if active_symptoms else [],
            top_hypothesis=top_hypothesis,
            confidence_pct=confidence_pct,
            recommended_actions=rec_actions,
            cited_documents=cited_documents or [],
            validation_status=status,
            validation_issues=critical_msgs + warning_msgs,
            operator_feedback=operator_feedback,
        )

        return ValidationReport(
            session_id=session_id,
            is_valid=is_valid,
            status=status,
            unit_issues=unit_issues,
            freshness_issues=fresh_issues,
            consistency_issues=consistency_issues,
            safety_violations=safety_violations,
            critical_messages=critical_msgs,
            warning_messages=warning_msgs,
            risk_score=risk_score,
            audit_record_hash=audit_rec.record_hash,
        )
