"""Fault scenario definitions and runtime dynamic fault injector.

Covers:
1. ScenarioType.NOMINAL: Baseline normal operation with standard turbulence.
2. ScenarioType.PCV_STICTION: Gas export control valve (PCV-101) stiction or failure closed/open.
3. ScenarioType.LIQUID_CARRYOVER: Foaming and severe droplet entrainment into demister and suction scrubber V-102.
4. ScenarioType.COMPRESSOR_SURGE: Compressor recycle failure or flow restriction causing surge oscillations and vibration.
5. ScenarioType.EMULSION_PAD: Interface emulsion layer growth causing LT-102 transmitter drift and oil/water separation degradation.
6. ScenarioType.SLUG_INFLUX: Transient multiphase slug surge from incoming flowline.
"""

from dataclasses import dataclass, field
from enum import Enum
import math
from typing import Dict, Any, Optional
from .process_model import SeparatorCompressorTrain


class ScenarioType(str, Enum):
    NOMINAL = "NOMINAL"
    PCV_STICTION = "PCV_101_STICTION"
    LIQUID_CARRYOVER = "LIQUID_CARRYOVER_DEMISTER_FOULING"
    COMPRESSOR_SURGE = "COMPRESSOR_K101_SURGE"
    EMULSION_PAD = "EMULSION_PAD_LT102_DRIFT"
    SLUG_INFLUX = "WELLHEAD_SLUG_INFLUX"


@dataclass
class FaultConfig:
    """Configuration for a specific fault injection event."""
    scenario_type: ScenarioType
    start_time_sec: float = 60.0
    duration_sec: float = 300.0
    severity: float = 0.8  # Normalized severity [0.1, 1.0]
    parameters: Dict[str, Any] = field(default_factory=dict)


class ScenarioInjector:
    """Manages scenario lifecycle, applying fault perturbations at specified simulation time."""

    def __init__(self, fault_config: Optional[FaultConfig] = None):
        self.config = fault_config or FaultConfig(scenario_type=ScenarioType.NOMINAL)

    def apply(self, train: SeparatorCompressorTrain) -> None:
        """Apply active perturbations to the process state based on simulation clock."""
        s = train.state
        c = self.config
        t = s.time_sec

        # Check if current simulation time is within the active fault window
        is_active = c.start_time_sec <= t < (c.start_time_sec + c.duration_sec)

        if not is_active:
            # Revert or decay perturbations to baseline
            s.pcv_stiction_active = False
            s.pcv_stuck_target = None
            s.demister_fouling_factor = 1.0
            s.foam_carryover_factor = 0.0
            s.interface_transmitter_bias_pct = 0.0
            s.inlet_slug_factor = 1.0
            return

        # Fault is active: modulate states according to scenario type
        if c.scenario_type == ScenarioType.PCV_STICTION:
            # Valve sticks at a degraded fixed position (e.g., pinched closed or wide open)
            stuck_position = c.parameters.get("stuck_position", 0.18 if c.severity > 0.5 else 0.85)
            s.pcv_stiction_active = True
            s.pcv_stuck_target = stuck_position

        elif c.scenario_type == ScenarioType.LIQUID_CARRYOVER:
            # Severe foaming in separator V-101 and demister pad blinding
            s.foam_carryover_factor = 1.2 * c.severity
            s.demister_fouling_factor = 1.0 + 3.8 * c.severity

        elif c.scenario_type == ScenarioType.COMPRESSOR_SURGE:
            # Suction flow restriction / recycle failure induces surge limit breach
            # Elevates surge limit flow above operating gas flow
            s.demister_fouling_factor = 1.0 + 2.0 * c.severity
            train.params.surge_flow_threshold_sm3h = 98000.0 * (1.0 + 0.15 * c.severity)

        elif c.scenario_type == ScenarioType.EMULSION_PAD:
            # Heavy emulsion layer creates sensor measurement drift in LT-102
            # Measured level reads 15-25% lower than true interface level
            drift_direction = c.parameters.get("drift_pct", -18.0 * c.severity)
            s.interface_transmitter_bias_pct = drift_direction

        elif c.scenario_type == ScenarioType.SLUG_INFLUX:
            # Periodic liquid/gas slug surges from upstream pipeline
            freq = 0.05  # 20 second period
            slug_wave = 1.0 + (0.45 * c.severity) * math.sin(2.0 * math.pi * freq * (t - c.start_time_sec))
            s.inlet_slug_factor = max(0.5, slug_wave)
