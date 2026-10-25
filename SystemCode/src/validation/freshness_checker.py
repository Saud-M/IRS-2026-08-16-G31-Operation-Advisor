"""Telemetry Freshness and Sensor Signal Quality Checker.

Verifies:
1. Telemetry Latency: Validates sample timestamp freshness (delta t <= 30s) to prevent
   diagnosing on stale, obsolete process readings.
2. Flatline / Frozen Transmitter: Detects frozen signals (zero variance over consecutive cycles).
3. Unphysical Slew Rate / Disconnect: Detects instrument wire breaks (step change > max plausible rate).
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple, Deque
from collections import deque


@dataclass
class FreshnessIssue:
    check_name: str
    severity: str        # "CRITICAL", "WARNING"
    tag: str
    delta_seconds: Optional[float]
    message: str


class TelemetryFreshnessChecker:
    """Monitors telemetry packet latency and detects frozen sensor links."""

    # Maximum allowable latency in seconds before flagging telemetry as stale
    MAX_ALLOWABLE_LATENCY_SEC = 30.0

    # Maximum plausible physical rate of change per second
    MAX_SLEW_RATES = {
        "PT-101": 5.0,     # bar/s
        "PT-102": 5.0,     # bar/s
        "LT-101": 5.0,     # %/s
        "LT-102": 4.0,     # %/s
        "VT-101": 10.0,    # mm/s per s
    }

    def __init__(self, history_len: int = 5):
        self.history_len = history_len
        self.sensor_buffers: Dict[str, Deque[float]] = {}

    def check_freshness(
        self,
        telemetry: Dict[str, Any],
        sample_timestamp: Optional[datetime] = None,
        current_time: Optional[datetime] = None,
    ) -> Tuple[bool, List[FreshnessIssue]]:
        """Evaluate telemetry freshness and signal stability."""
        issues: List[FreshnessIssue] = []
        now = current_time or datetime.now(timezone.utc)

        # 1. Timestamp Freshness Check
        if sample_timestamp:
            # Normalize to UTC
            if sample_timestamp.tzinfo is None:
                sample_utc = sample_timestamp.replace(tzinfo=timezone.utc)
            else:
                sample_utc = sample_timestamp.astimezone(timezone.utc)

            latency = abs((now - sample_utc).total_seconds())

            if latency > self.MAX_ALLOWABLE_LATENCY_SEC:
                issues.append(
                    FreshnessIssue(
                        check_name="STALE_TELEMETRY_DATA",
                        severity="CRITICAL",
                        tag="SYSTEM",
                        delta_seconds=round(latency, 2),
                        message=(
                            f"Telemetry snapshot is {latency:.1f}s old (threshold: {self.MAX_ALLOWABLE_LATENCY_SEC}s). "
                            "Advisory engine suspended until fresh DCS feed is restored."
                        ),
                    )
                )

        # 2. Slew Rate and Flatline Verification
        for tag, max_rate in self.MAX_SLEW_RATES.items():
            if tag not in telemetry:
                continue
            val = telemetry[tag]
            if not isinstance(val, (int, float)):
                continue

            if tag not in self.sensor_buffers:
                self.sensor_buffers[tag] = deque(maxlen=self.history_len)

            buf = self.sensor_buffers[tag]

            # Check sudden discontinuous step change
            if len(buf) > 0:
                prev_val = buf[-1]
                rate = abs(val - prev_val)
                if rate > max_rate:
                    issues.append(
                        FreshnessIssue(
                            check_name="SENSOR_DISCONTINUITY_SPIKE",
                            severity="WARNING",
                            tag=tag,
                            delta_seconds=None,
                            message=(
                                f"Sensor {tag} exhibited step change of {rate:.2f} units, "
                                f"exceeding max plausible slew rate of {max_rate:.2f}/s. Check wiring/transmitter."
                            ),
                        )
                    )

            buf.append(float(val))

            # Check flatline / frozen instrument if buffer is full
            if len(buf) == self.history_len:
                if len(set(buf)) == 1 and abs(buf[0]) > 1e-4:
                    issues.append(
                        FreshnessIssue(
                            check_name="FROZEN_SENSOR_FLATLINE",
                            severity="WARNING",
                            tag=tag,
                            delta_seconds=None,
                            message=f"Sensor {tag} has maintained identical value ({buf[0]}) over {self.history_len} consecutive polls.",
                        )
                    )

        is_valid = not any(iss.severity == "CRITICAL" for iss in issues)
        return is_valid, issues

    def reset(self):
        """Clear sensor history buffers."""
        self.sensor_buffers.clear()
