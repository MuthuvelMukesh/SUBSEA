from __future__ import annotations

from dataclasses import asdict

import numpy as np

from .models import Scenario, SensorObservation, VesselObservation

SUPPORTED_SCENARIOS = frozenset({"S01", "S02", "S04", "S05", "S07", "S17", "S18", "S19"})


def make_scenario(scenario_id: str = "S04", seed: int = 42) -> Scenario:
    definitions = {
        "S01": ("normal", False, False),
        "S02": ("physical disturbance", False, True),
        "S04": ("vessel plus disturbance", True, True),
        "S05": ("environmental event", False, True),
        "S07": ("sensor failure", True, True),
        "S17": ("AIS spoofing", True, True),
        "S18": ("transponder suppression", True, True),
        "S19": ("timestamp manipulation", True, True),
    }
    if scenario_id not in SUPPORTED_SCENARIOS:
        raise ValueError(f"unsupported scenario: {scenario_id}")
    description, vessel, disturbance = definitions[scenario_id]
    return Scenario(scenario_id, description, seed, vessel, disturbance, environmental_event=scenario_id == "S05", sensor_failure=scenario_id == "S07", spoofing=scenario_id == "S17", timestamp_manipulation=scenario_id == "S19")


def generate_observations(scenario: Scenario, *, samples: int = 256, sampling_rate: float = 50.0) -> tuple[list[SensorObservation], VesselObservation | None]:
    rng = np.random.default_rng(scenario.seed)
    timestamps = np.arange(samples) / sampling_rate
    amplitude = 0.15 if not scenario.disturbance_present else 1.8
    signal = amplitude * np.sin(2 * np.pi * 8 * timestamps)
    if scenario.environmental_event:
        signal = 0.55 * np.sin(2 * np.pi * 2 * timestamps)
    observations: list[SensorObservation] = []
    for index, timestamp in enumerate(timestamps):
        packet_received = not scenario.sensor_failure and rng.random() >= scenario.packet_loss
        vector = (1.0 + signal[index] + rng.normal(0, 0.03), rng.normal(0, 0.03), rng.normal(0, 0.03))
        observations.append(SensorObservation("sim-node-01", float(timestamp), vector, (0.0, 0.0), packet_received=packet_received))
    vessel = None
    if scenario.vessel_present:
        vessel_timestamp = float(timestamps[-1]) + (10.0 if scenario.timestamp_manipulation else 0.0)
        position = (2.0, 1.0)
        if scenario.spoofing:
            position = (25.0, 25.0)
        vessel = VesselObservation("vessel-01", vessel_timestamp, position, 4.0, 90.0, reported=not scenario.scenario_id == "S18")
    return observations, vessel


def scenario_manifest(scenario: Scenario) -> dict[str, object]:
    return asdict(scenario)
