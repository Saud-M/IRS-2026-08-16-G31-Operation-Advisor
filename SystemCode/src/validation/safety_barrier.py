"""Safety Barrier & Human-in-the-Loop Interlock Validator.

Enforces:
1. Read-Only Control Barrier: Absolute prohibition of automated write commands to plant
   Distributed Control Systems (DCS) or Safety Instrumented Systems (SIS/ESD).
2. Physical Action Interlocks: Prevents hazardous control actions (e.g. spurious flaring
   during normal pressure, or opening bypass without permit).
3. Human-in-the-Loop Enforcement: All recommendations must explicitly require human
   verification and console operator endorsement.
"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple


@dataclass
class SafetyViolation:
    check_name: str
    severity: str        # "CRITICAL", "WARNING"
    action_id: str
    target_equipment: str
    message: str
    mitigation: str


class SafetyBarrierValidator:
    """Enforces plant safety interlocks and read-only supervisory boundaries."""

    # Disallowed automated writes - advisory engine MUST NEVER issue automated DCS setpoint overwrites
    PROHIBITED_DIRECT_WRITES = [
        "WRITE_DCS_CONTROLLER_SP",
        "OVERRIDE_ESD_LOGIC",
        "FORCE_TRIP_TURBINE",
        "BYPASS_SAFETY_INSTRUMENTED_SYSTEM",
    ]

    def validate_action_plan(
        self,
        plan_steps: List[Dict[str, Any]],
        telemetry: Dict[str, Any],
        permit_to_work_granted: bool = True,
    ) -> Tuple[bool, List[SafetyViolation]]:
        """Validate candidate response plan against plant physical interlocks."""
        violations: List[SafetyViolation] = []
        pt101 = telemetry.get("PT-101", 31.0)

        for step in plan_steps:
            act_id = step.get("action_id", "")
            target_eq = step.get("target_equipment", "")

            # 1. Human-in-the-Loop DCS Direct Write Check
            if any(forbidden in act_id for forbidden in self.PROHIBITED_DIRECT_WRITES):
                violations.append(
                    SafetyViolation(
                        check_name="PROHIBITED_AUTOMATED_WRITE_COMMAND",
                        severity="CRITICAL",
                        action_id=act_id,
                        target_equipment=target_eq,
                        message=(
                            f"Safety Boundary Breach: Action {act_id} attempts automated write/override to plant controls. "
                            "Operation Advisor is strictly an advisory decision-support system."
                        ),
                        mitigation="Convert action to manual advisory checklist item for human operator execution.",
                    )
                )

            # 2. Interlock: Manual Flare Valve BDV-101 Spurious Flaring
            if act_id == "ACT_06_DIVERT_TO_FLARE":
                if pt101 < 33.5:
                    violations.append(
                        SafetyViolation(
                            check_name="SPURIOUS_FLARING_INTERLOCK_VIOLATION",
                            severity="CRITICAL",
                            action_id=act_id,
                            target_equipment=target_eq,
                            message=(
                                f"Interlock Block: Opening emergency flare blowdown BDV-101 is prohibited "
                                f"while separator pressure PT-101 ({pt101:.1f} barg) is within safe envelope (< 33.5 barg)."
                            ),
                            mitigation="Remove flare diversion step; utilize normal process control valves or manual bypass.",
                        )
                    )

            # 3. Interlock: Manual Bypass Valve HV-101B Permit Requirement
            if act_id == "ACT_01_SWITCH_MANUAL_BYPASS":
                if not permit_to_work_granted:
                    violations.append(
                        SafetyViolation(
                            check_name="PERMIT_TO_WORK_REQUIRED",
                            severity="CRITICAL",
                            action_id=act_id,
                            target_equipment=target_eq,
                            message="Physical interlock: Manual bypass HV-101B operation requires authorized Permit-to-Work (PTW).",
                            mitigation="Obtain shift superintendent hot work / bypass permit endorsement before unlocking valve stem.",
                        )
                    )

        is_valid = not any(v.severity == "CRITICAL" for v in violations)
        return is_valid, violations
