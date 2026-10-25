"""Batch Telemetry Dataset Generator for Machine Learning & Bayesian Reasoning.

Simulates multiple independent operational runs across all 6 scenario types
(Nominal + 5 Fault Scenarios) with randomized severities, duration, and onsets.
Produces standard structured Parquet and CSV files for model training.
"""

from dataclasses import asdict
import json
import os
import random
from typing import List, Dict, Any, Optional
import pandas as pd

from .process_model import SeparatorCompressorTrain, ProcessParameters
from .scenarios import ScenarioType, ScenarioInjector, FaultConfig
from .sensor_noise import SensorSuite, AlarmLevel


class TelemetryDataGenerator:
    """Generates synthetic process operations datasets across multiple scenario episodes."""

    def __init__(self, output_dir: str = "data/simulation", random_seed: int = 42):
        self.output_dir = output_dir
        self.random_seed = random_seed
        self.sensor_suite = SensorSuite(seed=random_seed)
        os.makedirs(output_dir, exist_ok=True)

    def generate_episode(
        self,
        scenario_type: ScenarioType,
        episode_id: int,
        duration_sec: float = 600.0,
        dt: float = 1.0,
        fault_start_sec: float = 120.0,
        fault_duration_sec: float = 360.0,
        severity: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Simulate a single continuous operational episode and record sensor observations."""
        if severity is None:
            severity = random.uniform(0.4, 0.95) if scenario_type != ScenarioType.NOMINAL else 0.0

        config = FaultConfig(
            scenario_type=scenario_type,
            start_time_sec=fault_start_sec,
            duration_sec=fault_duration_sec,
            severity=severity,
        )

        injector = ScenarioInjector(config)
        train = SeparatorCompressorTrain()

        records: List[Dict[str, Any]] = []
        steps = int(duration_sec / dt)

        for step_idx in range(steps):
            injector.apply(train)
            train.step(dt=dt)
            snapshot = train.snapshot()
            curr_time = train.state.time_sec

            # Sample noisy sensor readings
            readings = self.sensor_suite.sample_all(snapshot, curr_time)

            is_fault_active = (
                scenario_type != ScenarioType.NOMINAL
                and (fault_start_sec <= curr_time < fault_start_sec + fault_duration_sec)
            )

            record = {
                "episode_id": episode_id,
                "time_sec": curr_time,
                "scenario_label": scenario_type.value,
                "fault_active": int(is_fault_active),
                "fault_severity": round(severity if is_fault_active else 0.0, 3),
                # Sensor Measurements (with noise)
                "PT-101": readings["PT-101"].value,
                "LT-101": readings["LT-101"].value,
                "LT-102": readings["LT-102"].value,
                "TT-101": readings["TT-101"].value,
                "FT-101": readings["FT-101"].value,
                "DP-101": readings["DP-101"].value,
                "ST-101": readings["ST-101"].value,
                # Actuators and Internals
                "PCV-101_pos": snapshot["PCV-101_pos"],
                "LCV-101_pos": snapshot["LCV-101_pos"],
                "LCV-102_pos": snapshot["LCV-102_pos"],
                "V102_scrubber_level": snapshot["V102_scrubber_level"],
                "compressor_power_kw": snapshot["compressor_power_kw"],
                "surge_margin_pct": snapshot["surge_margin_pct"],
                "in_surge": int(snapshot["in_surge"]),
                # Alarm States
                "alarm_PT-101": readings["PT-101"].alarm.value,
                "alarm_LT-101": readings["LT-101"].alarm.value,
                "alarm_LT-102": readings["LT-102"].alarm.value,
                "alarm_FT-101": readings["FT-101"].alarm.value,
                "alarm_DP-101": readings["DP-101"].alarm.value,
                "alarm_ST-101": readings["ST-101"].alarm.value,
            }
            records.append(record)

        return records

    def generate_full_dataset(
        self,
        episodes_per_scenario: int = 5,
        episode_duration_sec: float = 400.0,
        dt: float = 1.0,
    ) -> pd.DataFrame:
        """Run batch simulation across all scenarios and save compiled telemetry dataset."""
        all_records: List[Dict[str, Any]] = []
        episode_counter = 1

        scenarios = [
            ScenarioType.NOMINAL,
            ScenarioType.PCV_STICTION,
            ScenarioType.LIQUID_CARRYOVER,
            ScenarioType.COMPRESSOR_SURGE,
            ScenarioType.EMULSION_PAD,
            ScenarioType.SLUG_INFLUX,
        ]

        for sc in scenarios:
            for ep in range(episodes_per_scenario):
                # Add randomized variations in fault onset and severity
                start_sec = random.uniform(60.0, 120.0)
                dur_sec = random.uniform(200.0, 260.0)
                sev = random.uniform(0.55, 0.95)

                records = self.generate_episode(
                    scenario_type=sc,
                    episode_id=episode_counter,
                    duration_sec=episode_duration_sec,
                    dt=dt,
                    fault_start_sec=start_sec,
                    fault_duration_sec=dur_sec,
                    severity=sev,
                )
                all_records.extend(records)
                episode_counter += 1

        df = pd.DataFrame(all_records)

        # Save to CSV and Parquet
        csv_path = os.path.join(self.output_dir, "telemetry_timeseries.csv")
        df.to_csv(csv_path, index=False)

        try:
            parquet_path = os.path.join(self.output_dir, "telemetry_timeseries.parquet")
            df.to_parquet(parquet_path, index=False)
        except Exception:
            # Fallback if pyarrow is not yet installed
            parquet_path = None

        # Write metadata JSON
        metadata = {
            "total_rows": len(df),
            "total_episodes": episode_counter - 1,
            "sampling_interval_sec": dt,
            "scenarios_included": [s.value for s in scenarios],
            "class_distribution": df["scenario_label"].value_counts().to_dict(),
            "fault_active_rows": int(df["fault_active"].sum()),
            "nominal_rows": int((df["fault_active"] == 0).sum()),
            "files": {
                "csv": csv_path,
                "parquet": parquet_path,
            },
        }

        with open(os.path.join(self.output_dir, "dataset_metadata.json"), "w") as f:
            json.dump(metadata, f, indent=2)

        return df


if __name__ == "__main__":
    generator = TelemetryDataGenerator()
    print("Generating standard simulation dataset...")
    df = generator.generate_full_dataset(episodes_per_scenario=4, episode_duration_sec=420.0)
    print(f"Generated {len(df)} telemetry rows across {df['episode_id'].nunique()} episodes.")
