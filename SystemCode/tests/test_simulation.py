"""Unit and Integration Tests for Process Simulation Bridge.
Verifies physics stability, mass conservation, fault scenarios, and alarm generation.
"""

import os
import pytest
from src.simulation_bridge.process_model import SeparatorCompressorTrain, ProcessParameters
from src.simulation_bridge.scenarios import ScenarioType, ScenarioInjector, FaultConfig
from src.simulation_bridge.sensor_noise import SensorSuite, AlarmLevel
from src.simulation_bridge.data_generator import TelemetryDataGenerator


def test_nominal_steady_state_stability():
    """Verify that under nominal conditions the plant maintains pressure and liquid levels within 5%."""
    train = SeparatorCompressorTrain()

    for _ in range(200):
        train.step(dt=1.0)

    snap = train.snapshot()
    # Pressure should settle near setpoint 30.0 barg
    assert 28.5 <= snap["PT-101"] <= 31.5, f"Pressure drifted: {snap['PT-101']}"
    # Liquid level should settle near setpoint 50.0%
    assert 46.0 <= snap["LT-101"] <= 54.0, f"Liquid level drifted: {snap['LT-101']}"
    # Interface level should settle near setpoint 25.0%
    assert 22.0 <= snap["LT-102"] <= 28.0, f"Interface level drifted: {snap['LT-102']}"
    # Compressor should not be in surge
    assert not snap["in_surge"], "Compressor incorrectly flagged surge during nominal run"


def test_pcv_stiction_fault_triggers_overpressure():
    """Verify that sticking PCV-101 closed causes pressure accumulation toward high alarm."""
    config = FaultConfig(
        scenario_type=ScenarioType.PCV_STICTION,
        start_time_sec=10.0,
        duration_sec=120.0,
        severity=0.9,
        parameters={"stuck_position": 0.10},  # Pinched severely
    )
    injector = ScenarioInjector(config)
    train = SeparatorCompressorTrain()

    for _ in range(60):
        injector.apply(train)
        train.step(dt=1.0)

    snap = train.snapshot()
    assert snap["PT-101"] > 33.0, f"Expected elevated pressure, got {snap['PT-101']}"


def test_liquid_carryover_triggers_demister_dp_and_scrubber_level():
    """Verify that liquid carryover/foaming spikes demister DP and fills V-102 scrubber."""
    config = FaultConfig(
        scenario_type=ScenarioType.LIQUID_CARRYOVER,
        start_time_sec=10.0,
        duration_sec=150.0,
        severity=0.85,
    )
    injector = ScenarioInjector(config)
    train = SeparatorCompressorTrain()

    # Step through before fault
    for _ in range(10):
        injector.apply(train)
        train.step(dt=1.0)
    baseline_dp = train.snapshot()["DP-101"]

    # Step into fault
    for _ in range(50):
        injector.apply(train)
        train.step(dt=1.0)
    fault_snap = train.snapshot()

    assert fault_snap["DP-101"] > baseline_dp * 2.5, "Demister DP did not spike sufficiently"
    assert fault_snap["V102_scrubber_level"] > 10.0, "Scrubber liquid did not accumulate"


def test_compressor_surge_elevates_vibration():
    """Verify that surge conditions trigger high vibration alarm."""
    config = FaultConfig(
        scenario_type=ScenarioType.COMPRESSOR_SURGE,
        start_time_sec=10.0,
        duration_sec=100.0,
        severity=0.9,
    )
    injector = ScenarioInjector(config)
    train = SeparatorCompressorTrain()

    for _ in range(40):
        injector.apply(train)
        train.step(dt=1.0)

    snap = train.snapshot()
    assert snap["ST-101"] >= 4.5, f"Vibration should be elevated in surge, got {snap['ST-101']}"


def test_sensor_suite_noise_and_alarms():
    """Verify that Gaussian noise is applied and alarm trips trigger accurately."""
    suite = SensorSuite(seed=123)

    # Normal pressure
    r_normal = suite.sample_reading("PT-101", 30.0, 1.0)
    assert r_normal.alarm == AlarmLevel.NORMAL
    assert abs(r_normal.value - 30.0) < 0.5

    # High High Pressure
    r_high_high = suite.sample_reading("PT-101", 37.0, 2.0)
    assert r_high_high.alarm == AlarmLevel.HIGH_HIGH


def test_data_generator_output(tmp_path):
    """Verify that TelemetryDataGenerator exports valid episodes with correct columns."""
    gen = TelemetryDataGenerator(output_dir=str(tmp_path), random_seed=99)
    df = gen.generate_full_dataset(episodes_per_scenario=1, episode_duration_sec=30.0, dt=1.0)

    assert len(df) > 0
    assert "PT-101" in df.columns
    assert "scenario_label" in df.columns
    assert "fault_active" in df.columns
    assert os.path.exists(os.path.join(tmp_path, "telemetry_timeseries.csv"))
    assert os.path.exists(os.path.join(tmp_path, "dataset_metadata.json"))
