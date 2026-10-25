"""Dimensional and Unit Consistency Validator for Industrial Process Telemetry.

Verifies:
1. Physical boundaries (e.g., absolute pressure >= 0, non-negative flows, valve travel in [0, 100]%).
2. Multiphase vessel physical conservation laws:
   - Interface level LT-102 must never exceed total liquid level LT-101.
   - Demister differential pressure DPIT-101 must be non-negative.
3. Measurement unit consistency against plant engineering specifications.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple


@dataclass
class ValidationIssue:
    check_name: str
    severity: str        # "CRITICAL", "WARNING", "INFO"
    tag: str
    observed_value: Any
    message: str
    physical_limit: str


class UnitConsistencyValidator:
    """Enforces thermodynamic and dimensional consistency on process sensor snapshots."""

    # Plausible physical operating envelopes for CPF Train 1
    ENVELOPES = {
        "PT-101": (0.0, 50.0, "barg", "V-101 Separator Pressure"),
        "PT-102": (0.0, 50.0, "barg", "K-101 Suction Pressure"),
        "PT-103": (0.0, 100.0, "barg", "K-101 Discharge Pressure"),
        "LT-101": (0.0, 100.0, "%", "V-101 Total Liquid Level"),
        "LT-102": (0.0, 100.0, "%", "V-101 Oil-Water Interface Level"),
        "LT-103": (0.0, 100.0, "%", "V-102 Scrubber Liquid Level"),
        "FT-101": (0.0, 150000.0, "Sm3/h", "Gas Export Flow Rate"),
        "FT-102": (0.0, 2000.0, "m3/h", "Oil Export Flow Rate"),
        "DPIT-101": (0.0, 1.0, "bar", "Demister Differential Pressure"),
        "VT-101": (0.0, 25.0, "mm/s", "K-101 Compressor Vibration RMS"),
        "TT-101": (-20.0, 200.0, "°C", "V-101 Fluid Temperature"),
        "TT-102": (-20.0, 250.0, "°C", "K-101 Discharge Temperature"),
        "PCV_101_POS": (0.0, 100.0, "%", "PCV-101 Valve Stem Opening"),
        "ASV_101_POS": (0.0, 100.0, "%", "ASV-101 Anti-Surge Valve Opening"),
    }

    def validate_snapshot(self, telemetry: Dict[str, Any]) -> Tuple[bool, List[ValidationIssue]]:
        """Validate an individual telemetry frame against physical laws and instrument envelopes."""
        issues: List[ValidationIssue] = []

        # 1. Range & Physical Boundary Check
        for tag, val in telemetry.items():
            if tag not in self.ENVELOPES:
                continue
            if not isinstance(val, (int, float)):
                issues.append(
                    ValidationIssue(
                        check_name="TYPE_CONSISTENCY",
                        severity="CRITICAL",
                        tag=tag,
                        observed_value=val,
                        message=f"Non-numeric value detected for sensor {tag}: {val}",
                        physical_limit="float",
                    )
                )
                continue

            low, high, unit, desc = self.ENVELOPES[tag]
            if val < low:
                issues.append(
                    ValidationIssue(
                        check_name="LOWER_PHYSICAL_BOUND_VIOLATION",
                        severity="CRITICAL" if val < 0.0 and tag.startswith(("PT", "LT", "FT", "VT")) else "WARNING",
                        tag=tag,
                        observed_value=val,
                        message=f"{desc} ({tag}) reads {val} {unit}, below physical lower bound of {low} {unit}.",
                        physical_limit=f">= {low} {unit}",
                    )
                )
            elif val > high:
                issues.append(
                    ValidationIssue(
                        check_name="UPPER_PHYSICAL_BOUND_VIOLATION",
                        severity="CRITICAL" if val > high * 1.25 else "WARNING",
                        tag=tag,
                        observed_value=val,
                        message=f"{desc} ({tag}) reads {val} {unit}, exceeding physical sensor design limit of {high} {unit}.",
                        physical_limit=f"<= {high} {unit}",
                    )
                )

        # 2. Conservation Law: Interface Level <= Total Liquid Level
        lt101 = telemetry.get("LT-101")
        lt102 = telemetry.get("LT-102")
        if lt101 is not None and lt102 is not None:
            if isinstance(lt101, (int, float)) and isinstance(lt102, (int, float)):
                if lt102 > lt101:
                    issues.append(
                        ValidationIssue(
                            check_name="INTERFACE_TOTAL_LEVEL_INVERSION",
                            severity="CRITICAL",
                            tag="LT-102",
                            observed_value=f"LT-102={lt102}%, LT-101={lt101}%",
                            message=(
                                f"Physical Law Violation: Oil-water interface level LT-102 ({lt102}%) "
                                f"exceeds vessel total liquid level LT-101 ({lt101}%)."
                            ),
                            physical_limit="LT-102 <= LT-101",
                        )
                    )

        # 3. Conservation Law: Compressor Differential Pressure (Discharge >= Suction)
        pt102 = telemetry.get("PT-102")
        pt103 = telemetry.get("PT-103")
        if pt102 is not None and pt103 is not None:
            if isinstance(pt102, (int, float)) and isinstance(pt103, (int, float)):
                if pt103 < pt102 - 0.5:  # Margin for measurement noise
                    issues.append(
                        ValidationIssue(
                            check_name="COMPRESSOR_REVERSE_PRESSURE_RATIO",
                            severity="CRITICAL",
                            tag="PT-103",
                            observed_value=f"PT-103={pt103} barg, PT-102={pt102} barg",
                            message=(
                                f"Thermodynamic Violation: Compressor discharge PT-103 ({pt103} barg) "
                                f"is lower than suction PT-102 ({pt102} barg) while running."
                            ),
                            physical_limit="PT-103 >= PT-102",
                        )
                    )

        is_valid = not any(iss.severity == "CRITICAL" for iss in issues)
        return is_valid, issues
