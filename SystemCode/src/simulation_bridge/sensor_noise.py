"""Sensor Noise Models, Calibration, and Industrial Alarm Threshold Monitors.

Implements:
1. Zero-mean Gaussian noise modeling for realistic instrument telemetry:
   x_measured = x_true + N(0, sigma^2)
2. Industrial alarm state classification:
   - NORMAL
   - HIGH (AH) / HIGH_HIGH (AHH)
   - LOW (AL) / LOW_LOW (ALL)
3. SensorSuite mapping tags to engineering units and physical ranges.
"""

from dataclasses import dataclass
from enum import Enum
import random
from typing import Dict, Any, List, Optional


class AlarmLevel(str, Enum):
    NORMAL = "NORMAL"
    LOW_LOW = "LOW_LOW"
    LOW = "LOW"
    HIGH = "HIGH"
    HIGH_HIGH = "HIGH_HIGH"


@dataclass
class SensorSpec:
    tag: str
    name: str
    unit: str
    noise_std: float
    low_low: Optional[float] = None
    low: Optional[float] = None
    high: Optional[float] = None
    high_high: Optional[float] = None


@dataclass
class SensorReading:
    tag: str
    name: str
    unit: str
    value: float
    true_value: float
    alarm: AlarmLevel
    timestamp_sec: float


class SensorSuite:
    """Manages noise perturbation and alarm classification across all process instruments."""

    SPECS: Dict[str, SensorSpec] = {
        "PT-101": SensorSpec(
            tag="PT-101",
            name="Separator V-101 Pressure",
            unit="barg",
            noise_std=0.08,
            low=26.0,
            high=34.0,
            high_high=36.5,
        ),
        "LT-101": SensorSpec(
            tag="LT-101",
            name="Separator Oil Liquid Level",
            unit="%",
            noise_std=0.35,
            low_low=20.0,
            low=25.0,
            high=70.0,
            high_high=85.0,
        ),
        "LT-102": SensorSpec(
            tag="LT-102",
            name="Separator Water Interface Level",
            unit="%",
            noise_std=0.25,
            low_low=8.0,
            low=10.0,
            high=40.0,
            high_high=50.0,
        ),
        "TT-101": SensorSpec(
            tag="TT-101",
            name="Inlet Stream Temperature",
            unit="°C",
            noise_std=0.15,
            low=25.0,
            high=65.0,
        ),
        "FT-101": SensorSpec(
            tag="FT-101",
            name="Gas Export Flow Rate",
            unit="Sm3/h",
            noise_std=450.0,
            low=60000.0,
            high=110000.0,
        ),
        "DP-101": SensorSpec(
            tag="DP-101",
            name="Suction Demister Differential Pressure",
            unit="bar",
            noise_std=0.005,
            high=0.45,
            high_high=0.60,
        ),
        "ST-101": SensorSpec(
            tag="ST-101",
            name="Compressor K-101 Shaft Vibration",
            unit="mm/s",
            noise_std=0.08,
            high=4.5,
            high_high=7.1,
        ),
    }

    def __init__(self, seed: Optional[int] = 42):
        if seed is not None:
            random.seed(seed)

    def sample_reading(self, tag: str, true_value: float, timestamp_sec: float) -> SensorReading:
        """Sample a noisy observation and classify its alarm condition."""
        spec = self.SPECS.get(tag)
        if spec is None:
            return SensorReading(
                tag=tag,
                name=tag,
                unit="",
                value=true_value,
                true_value=true_value,
                alarm=AlarmLevel.NORMAL,
                timestamp_sec=timestamp_sec,
            )

        # Add Gaussian noise
        noisy_val = true_value + random.gauss(0.0, spec.noise_std)
        alarm = self.evaluate_alarm(noisy_val, spec)

        return SensorReading(
            tag=tag,
            name=spec.name,
            unit=spec.unit,
            value=round(noisy_val, 4),
            true_value=round(true_value, 4),
            alarm=alarm,
            timestamp_sec=timestamp_sec,
        )

    def evaluate_alarm(self, val: float, spec: SensorSpec) -> AlarmLevel:
        """Classify measurement against trip points."""
        if spec.high_high is not None and val >= spec.high_high:
            return AlarmLevel.HIGH_HIGH
        if spec.high is not None and val >= spec.high:
            return AlarmLevel.HIGH
        if spec.low_low is not None and val <= spec.low_low:
            return AlarmLevel.LOW_LOW
        if spec.low is not None and val <= spec.low:
            return AlarmLevel.LOW
        return AlarmLevel.NORMAL

    def sample_all(self, state_dict: Dict[str, Any], timestamp_sec: float) -> Dict[str, SensorReading]:
        """Convert a state snapshot dictionary into full noisy sensor readings."""
        readings: Dict[str, SensorReading] = {}
        for tag in self.SPECS:
            if tag in state_dict:
                readings[tag] = self.sample_reading(tag, float(state_dict[tag]), timestamp_sec)
        return readings
