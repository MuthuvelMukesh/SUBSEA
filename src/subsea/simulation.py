from __future__ import annotations

from dataclasses import asdict
from collections.abc import Sequence

import numpy as np

from .models import Scenario, SensorObservation, VesselObservation

SUPPORTED_SCENARIOS = frozenset({f"S{index:02d}" for index in range(1, 23)})


def make_scenario(scenario_id: str = "S04", seed: int = 42) -> Scenario:
    definitions = {
        "S01": ("normal", False, False), "S02": ("physical disturbance", False, True), "S03": ("vessel only", True, False),
        "S04": ("vessel plus disturbance", True, True), "S05": ("environmental event", False, True), "S06": ("non-vessel mechanical event", False, True),
        "S07": ("sensor failure", True, True), "S08": ("communication failure", True, True), "S09": ("noise stress", False, True),
        "S10": ("packet loss", False, True), "S11": ("spatial mismatch", True, True), "S12": ("temporal mismatch", True, True),
        "S13": ("conflicting evidence", True, True), "S14": ("counter evidence", True, True), "S15": ("high uncertainty", True, True),
        "S16": ("absence of corroboration", True, True), "S17": ("AIS spoofing", True, True), "S18": ("transponder suppression", True, True),
        "S19": ("timestamp manipulation", True, True), "S20": ("spatial manipulation", True, True), "S21": ("combined adversarial evasion", True, True),
        "S22": ("multiple vessels and disturbances", True, True),
    }
    if scenario_id not in SUPPORTED_SCENARIOS:
        raise ValueError(f"unsupported scenario: {scenario_id}")
    description, vessel, disturbance = definitions[scenario_id]
    return Scenario(scenario_id, description, seed, vessel, disturbance, environmental_event=scenario_id == "S05", sensor_failure=scenario_id == "S07", packet_loss=0.5 if scenario_id == "S15" else (0.25 if scenario_id == "S10" else 0.0), spoofing=scenario_id in {"S17", "S20", "S21"}, timestamp_manipulation=scenario_id in {"S19", "S21"}, mechanical_event=scenario_id == "S06", communication_failure=scenario_id == "S08", noise_stress=scenario_id == "S09", spatial_mismatch=scenario_id == "S11", temporal_mismatch=scenario_id == "S12", conflicting_evidence=scenario_id == "S13", counter_evidence=scenario_id == "S14", absence_corroboration=scenario_id == "S16", multiple_targets=scenario_id == "S22")


def generate_vessels(scenario: Scenario, timestamps: Sequence[float]) -> tuple[VesselObservation, ...]:
    if not scenario.vessel_present:
        return ()
    vessel_timestamp = float(timestamps[-1]) + (10.0 if scenario.timestamp_manipulation else 0.0)
    position = (2.0, 1.0)
    if scenario.spatial_mismatch or scenario.counter_evidence or scenario.spoofing:
        position = (25.0, 25.0)
    if scenario.temporal_mismatch:
        vessel_timestamp += 20.0
    vessels = [VesselObservation("vessel-01", vessel_timestamp, position, 4.0, 90.0, reported=scenario.scenario_id not in {"S16", "S18"})]
    if scenario.multiple_targets:
        vessels.append(VesselObservation("vessel-02", vessel_timestamp, (-2.0, -1.0), 3.0, 270.0))
    return tuple(vessels)


def generate_observations(scenario: Scenario, *, samples: int = 256, sampling_rate: float = 50.0) -> tuple[list[SensorObservation], VesselObservation | None]:
    rng = np.random.default_rng(scenario.seed)
    timestamps = np.arange(samples) / sampling_rate
    amplitude = 0.15 if not scenario.disturbance_present else 1.8
    noise = 0.15 if scenario.noise_stress else 0.03
    signal = amplitude * np.sin(2 * np.pi * 8 * timestamps)
    if scenario.environmental_event:
        signal = 0.55 * np.sin(2 * np.pi * 2 * timestamps)
    if scenario.conflicting_evidence:
        signal = 0.55 * np.sin(2 * np.pi * 2 * timestamps)
    observations: list[SensorObservation] = []
    for index, timestamp in enumerate(timestamps):
        packet_received = not scenario.sensor_failure and not scenario.communication_failure and rng.random() >= scenario.packet_loss
        vector = (1.0 + signal[index] + rng.normal(0, noise), rng.normal(0, noise), rng.normal(0, noise))
        observations.append(SensorObservation("sim-node-01", float(timestamp), vector, (0.0, 0.0), packet_received=packet_received))
    vessels = generate_vessels(scenario, timestamps)
    vessel = vessels[0] if vessels else None
    return observations, vessel


def scenario_manifest(scenario: Scenario) -> dict[str, object]:
    return asdict(scenario)
