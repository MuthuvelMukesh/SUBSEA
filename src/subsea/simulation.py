from __future__ import annotations

from dataclasses import asdict, replace
from collections.abc import Sequence

import numpy as np

from .models import Scenario, SensorObservation, VesselObservation

SUPPORTED_SCENARIOS = frozenset({f"S{index:02d}" for index in range(1, 23)})

# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------

_DEFINITIONS: dict[str, tuple[str, bool, bool]] = {
    "S01": ("normal", False, False),
    "S02": ("physical disturbance", False, True),
    "S03": ("vessel only", True, False),
    "S04": ("vessel plus disturbance", True, True),
    "S05": ("environmental event", False, True),
    "S06": ("non-vessel mechanical event", False, True),
    "S07": ("sensor failure", True, True),
    "S08": ("communication failure", True, True),
    "S09": ("noise stress", False, True),
    "S10": ("packet loss", False, True),
    "S11": ("spatial mismatch", True, True),
    "S12": ("temporal mismatch", True, True),
    "S13": ("conflicting evidence", True, True),
    "S14": ("counter evidence", True, True),
    "S15": ("high uncertainty", True, True),
    "S16": ("absence of corroboration", True, True),
    "S17": ("AIS spoofing", True, True),
    "S18": ("transponder suppression", True, True),
    "S19": ("timestamp manipulation", True, True),
    "S20": ("spatial manipulation", True, True),
    "S21": ("combined adversarial evasion", True, True),
    "S22": ("multiple vessels and disturbances", True, True),
}


def make_scenario(scenario_id: str = "S04", seed: int = 42) -> Scenario:
    if scenario_id not in SUPPORTED_SCENARIOS:
        raise ValueError(f"unsupported scenario: {scenario_id}")
    description, vessel, disturbance = _DEFINITIONS[scenario_id]
    return Scenario(
        scenario_id, description, seed, vessel, disturbance,
        environmental_event=scenario_id == "S05",
        sensor_failure=scenario_id == "S07",
        packet_loss=0.5 if scenario_id == "S15" else (0.25 if scenario_id == "S10" else 0.0),
        spoofing=scenario_id in {"S17", "S21"},
        timestamp_manipulation=scenario_id in {"S19", "S21"},
        mechanical_event=scenario_id == "S06",
        communication_failure=scenario_id == "S08",
        noise_stress=scenario_id == "S09",
        spatial_mismatch=scenario_id == "S11",
        temporal_mismatch=scenario_id == "S12",
        conflicting_evidence=scenario_id == "S13",
        counter_evidence=scenario_id == "S14",
        absence_corroboration=scenario_id == "S16",
        multiple_targets=scenario_id == "S22",
        noise_level=0.30 if scenario_id == "S09" else 0.03,
        n_nodes=1,
        position_uncertainty_level=0.0,
        high_uncertainty=scenario_id == "S15",
        spatial_manipulation=scenario_id in {"S20", "S21"},
    )


# ---------------------------------------------------------------------------
# Vessel generation
# ---------------------------------------------------------------------------

def generate_vessels(
    scenario: Scenario,
    timestamps: Sequence[float],
) -> tuple[VesselObservation, ...]:
    if not scenario.vessel_present:
        return ()
    vessel_timestamp = float(timestamps[-1]) + (10.0 if scenario.timestamp_manipulation else 0.0)
    position: tuple[float, float] = (2.0, 1.0)
    if scenario.spatial_mismatch or scenario.counter_evidence or scenario.spoofing:
        position = (25.0, 25.0)
    if scenario.spatial_manipulation:
        position = (20.0, 20.0)
    if scenario.temporal_mismatch:
        vessel_timestamp += 20.0
    pos_unc = scenario.position_uncertainty_level
    vessels = [VesselObservation(
        "vessel-01", vessel_timestamp, position, 4.0, 90.0,
        reported=scenario.scenario_id not in {"S16", "S18"},
        position_uncertainty=pos_unc,
    )]
    if scenario.multiple_targets:
        vessels.append(VesselObservation(
            "vessel-02", vessel_timestamp, (-2.0, -1.0), 3.0, 270.0,
            position_uncertainty=pos_unc,
        ))
    return tuple(vessels)


def generate_multi_vessel(
    scenario: Scenario,
    timestamps: Sequence[float],
    n_vessels: int = 2,
    *,
    rng: np.random.Generator | None = None,
) -> tuple[VesselObservation, ...]:
    """Generate N vessels with diverse positions/speeds for multi-vessel evaluation."""
    if n_vessels <= 0:
        return ()
    if rng is None:
        rng = np.random.default_rng(scenario.seed + 9999)
    vessel_timestamp = float(timestamps[-1])
    vessels: list[VesselObservation] = []
    for i in range(n_vessels):
        # First vessel near cable, others progressively farther
        distance_factor = 1.0 + i * 5.0
        angle = rng.uniform(0, 2 * np.pi)
        x = distance_factor * np.cos(angle)
        y = distance_factor * np.sin(angle)
        speed = float(rng.uniform(1.0, 8.0))
        heading = float(rng.uniform(0, 360))
        vessels.append(VesselObservation(
            f"vessel-{i+1:02d}",
            vessel_timestamp + float(rng.uniform(-2.0, 2.0)),
            (float(x), float(y)),
            speed,
            heading,
            reported=True,
            position_uncertainty=scenario.position_uncertainty_level,
        ))
    return tuple(vessels)


# ---------------------------------------------------------------------------
# Single-node observation generation (backward compatible)
# ---------------------------------------------------------------------------

def generate_observations(
    scenario: Scenario,
    *,
    samples: int = 256,
    sampling_rate: float = 50.0,
    noise_override: float | None = None,
    packet_loss_override: float | None = None,
) -> tuple[list[SensorObservation], VesselObservation | None]:
    rng = np.random.default_rng(scenario.seed)
    timestamps = np.arange(samples) / sampling_rate
    amplitude = 0.15 if not scenario.disturbance_present else 1.8
    noise = noise_override if noise_override is not None else scenario.noise_level
    packet_loss = packet_loss_override if packet_loss_override is not None else scenario.packet_loss
    signal = amplitude * np.sin(2 * np.pi * 8 * timestamps)
    if scenario.environmental_event:
        signal = 0.55 * np.sin(2 * np.pi * 2 * timestamps)
    if scenario.mechanical_event:
        signal = 0.9 * np.sin(2 * np.pi * 5 * timestamps)
    if scenario.conflicting_evidence:
        signal = 0.55 * np.sin(2 * np.pi * 2 * timestamps)
    observations: list[SensorObservation] = []
    for index, timestamp in enumerate(timestamps):
        packet_received = (
            not scenario.sensor_failure
            and not scenario.communication_failure
            and rng.random() >= packet_loss
        )
        vector = (
            1.0 + signal[index] + rng.normal(0, noise),
            rng.normal(0, noise),
            rng.normal(0, noise),
        )
        observations.append(SensorObservation(
            "sim-node-01", float(timestamp), vector, (0.0, 0.0),
            packet_received=packet_received,
        ))
    vessels = generate_vessels(scenario, timestamps)
    vessel = vessels[0] if vessels else None
    return observations, vessel


# ---------------------------------------------------------------------------
# Multi-node observation generation
# ---------------------------------------------------------------------------

def generate_multi_node_observations(
    scenario: Scenario,
    *,
    n_nodes: int | None = None,
    samples: int = 256,
    sampling_rate: float = 50.0,
    cable_positions: tuple[tuple[float, float], ...] | None = None,
    disturbance_position: tuple[float, float] = (0.0, 0.0),
    attenuation_rate: float = 0.2,
    noise_override: float | None = None,
    packet_loss_override: float | None = None,
) -> tuple[dict[str, list[SensorObservation]], tuple[VesselObservation, ...]]:
    """Generate observations for N nodes along a cable.

    Each node receives the disturbance signal attenuated by distance from
    the disturbance source. Noise, health, and packet loss are independent
    per node.

    Returns:
        A dict mapping node_id to its observations, and the vessel tuple.
    """
    num_nodes = n_nodes if n_nodes is not None else max(scenario.n_nodes, 1)
    if num_nodes <= 0:
        raise ValueError("n_nodes must be positive")

    # Default cable positions: evenly spaced along x-axis
    if cable_positions is None:
        cable_positions = tuple(
            (float(i * 5.0), 0.0) for i in range(num_nodes)
        )
    if len(cable_positions) != num_nodes:
        raise ValueError("cable_positions length must match n_nodes")

    noise_base = noise_override if noise_override is not None else scenario.noise_level
    packet_loss_base = packet_loss_override if packet_loss_override is not None else scenario.packet_loss

    timestamps = np.arange(samples) / sampling_rate
    amplitude = 0.15 if not scenario.disturbance_present else 1.8
    base_signal = amplitude * np.sin(2 * np.pi * 8 * timestamps)
    if scenario.environmental_event:
        base_signal = 0.55 * np.sin(2 * np.pi * 2 * timestamps)
    if scenario.mechanical_event:
        base_signal = 0.9 * np.sin(2 * np.pi * 5 * timestamps)
    if scenario.conflicting_evidence:
        base_signal = 0.55 * np.sin(2 * np.pi * 2 * timestamps)

    all_observations: dict[str, list[SensorObservation]] = {}

    for node_index in range(num_nodes):
        node_id = f"sim-node-{node_index+1:02d}"
        node_pos = cable_positions[node_index]
        rng = np.random.default_rng(scenario.seed + node_index * 1000)

        # Spatial attenuation: signal weakens with distance from disturbance
        dist = np.sqrt(
            (node_pos[0] - disturbance_position[0]) ** 2
            + (node_pos[1] - disturbance_position[1]) ** 2
        )
        attenuation = np.exp(-attenuation_rate * dist)
        node_signal = base_signal * attenuation

        # Node-specific noise (scaled slightly per node)
        node_noise = noise_base * (1.0 + 0.1 * node_index)

        # Node-specific packet loss
        node_packet_loss = min(1.0, packet_loss_base + 0.02 * node_index)

        observations: list[SensorObservation] = []
        for index, timestamp in enumerate(timestamps):
            packet_received = (
                not scenario.sensor_failure
                and not scenario.communication_failure
                and rng.random() >= node_packet_loss
            )
            vector = (
                1.0 + node_signal[index] + rng.normal(0, node_noise),
                rng.normal(0, node_noise),
                rng.normal(0, node_noise),
            )
            observations.append(SensorObservation(
                node_id, float(timestamp), vector, node_pos,
                packet_received=packet_received,
            ))
        all_observations[node_id] = observations

    vessels = generate_vessels(scenario, timestamps)
    return all_observations, vessels


# ---------------------------------------------------------------------------
# Scenario manifest
# ---------------------------------------------------------------------------

def scenario_manifest(scenario: Scenario) -> dict[str, object]:
    return asdict(scenario)
