"""Read-only data extraction helpers for Subsea web export.

Extracts data from models, pipeline, simulation, manifests, and tables for
standalone browser presentation. Does not modify any pipeline or decision logic.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

import numpy as np

from .adversarial import SUPPORTED_ATTACKS, apply_attack
from .features import acceleration_magnitude, spectral_features
from .geometry import distance_to_polyline, nearest_point_on_polyline
from .models import DecisionResult, Hypothesis, Scenario, SensorObservation, VesselObservation
from .pipeline import run_pipeline
from .simulation import SUPPORTED_SCENARIOS, _DEFINITIONS, generate_observations, make_scenario
from .trajectory import closest_point_of_approach, crossing_detected, dwell_time


def export_meta(
    data_kind: str,
    source_manifest_path: str | None = None,
    seed: int = 42,
) -> dict[str, Any]:
    """Standard header for all exported web data files."""
    return {
        "software_version": "0.1.0",
        "data_kind": data_kind,
        "source_manifest_path": source_manifest_path or "N/A",
        "seed": seed,
        "exported_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


def unavailable_payload(command: str) -> dict[str, Any]:
    """Payload format for missing/uncomputed data per Hard Rule 3."""
    return {
        "status": "unavailable",
        "how_to_generate": command,
    }


def serialize_decision_result(result: DecisionResult) -> dict[str, Any]:
    """Convert a DecisionResult into a JSON-serializable dictionary."""
    return {
        "decision": result.decision.value,
        "physical_confidence": float(round(result.physical_confidence, 4)),
        "association_confidence": float(round(result.association_confidence, 4)),
        "reliability": float(round(result.reliability, 4)),
        "uncertainty": float(round(result.uncertainty, 4)),
        "hypothesis_scores": {k: float(round(v, 4)) for k, v in result.hypothesis_scores.items()},
        "positive_evidence": list(result.positive_evidence),
        "counter_evidence": list(result.counter_evidence),
        "missing_corroboration": list(result.missing_corroboration),
        "rationale": list(result.rationale),
        "audit": {
            "health": {
                "health": float(round(result.audit.get("health", {}).get("health", 1.0), 4)),
                "availability": float(round(result.audit.get("health", {}).get("availability", 1.0), 4)),
                "stale": bool(result.audit.get("health", {}).get("stale", False)),
                "reasons": list(result.audit.get("health", {}).get("reasons", ())),
            },
            "association_components": {
                k: float(round(v, 4))
                for k, v in result.audit.get("association_components", {}).items()
            },
            "uncertainty_components": {
                k: float(round(v, 4))
                for k, v in result.audit.get("uncertainty_components", {}).items()
            },
        },
    }


def export_scenario_catalog() -> list[dict[str, Any]]:
    """Return catalog of all 22 benchmark scenarios with verified labels from _DEFINITIONS."""
    catalog = []
    for sid in sorted(list(SUPPORTED_SCENARIOS)):
        desc, vessel_present, disturbance_present = _DEFINITIONS[sid]
        sc = make_scenario(sid, seed=42)
        catalog.append({
            "scenario_id": sid,
            "description": desc,
            "vessel_present": vessel_present,
            "disturbance_present": disturbance_present,
            "environmental_event": sc.environmental_event,
            "sensor_failure": sc.sensor_failure,
            "packet_loss": sc.packet_loss,
            "spoofing": sc.spoofing,
            "timestamp_manipulation": sc.timestamp_manipulation,
            "mechanical_event": sc.mechanical_event,
            "communication_failure": sc.communication_failure,
            "noise_stress": sc.noise_stress,
            "spatial_mismatch": sc.spatial_mismatch,
            "temporal_mismatch": sc.temporal_mismatch,
            "conflicting_evidence": sc.conflicting_evidence,
            "counter_evidence": sc.counter_evidence,
            "absence_corroboration": sc.absence_corroboration,
            "multiple_targets": sc.multiple_targets,
            "high_uncertainty": sc.high_uncertainty,
            "spatial_manipulation": sc.spatial_manipulation,
        })
    return catalog


def generate_scenario_runs(seed: int = 42) -> dict[str, dict[str, Any]]:
    """Precompute pipeline outputs for every scenario x attack x severity."""
    severities = [0.0, 0.25, 0.5, 0.75, 1.0]
    attacks = sorted(list(SUPPORTED_ATTACKS))
    runs: dict[str, dict[str, Any]] = {}

    for sid in sorted(list(SUPPORTED_SCENARIOS)):
        runs[sid] = {}
        sc = make_scenario(sid, seed=seed)
        obs, base_vessel = generate_observations(sc)

        for atk in attacks:
            runs[sid][atk] = {}
            active_severities = [0.0] if atk == "none" else severities
            for sev in active_severities:
                if base_vessel is not None and atk != "none":
                    vessel = apply_attack(base_vessel, atk, sev)
                else:
                    vessel = base_vessel

                result = run_pipeline(obs, vessel, environmental_event=sc.environmental_event)

                if vessel is not None:
                    dist_cable = float(round(distance_to_polyline(vessel.position, [(0.0, 0.0), (100.0, 0.0)]), 2))
                    vessel_info: dict[str, Any] | None = {
                        "vessel_id": vessel.vessel_id,
                        "timestamp": vessel.timestamp,
                        "position": [float(round(vessel.position[0], 2)), float(round(vessel.position[1], 2))],
                        "speed": float(round(vessel.speed, 2)),
                        "heading": float(round(vessel.heading, 1)),
                        "reported": vessel.reported,
                        "position_uncertainty": float(round(vessel.position_uncertainty, 2)),
                        "distance_to_cable_m": dist_cable,
                    }
                else:
                    vessel_info = None

                runs[sid][atk][str(sev)] = {
                    "result": serialize_decision_result(result),
                    "vessel": vessel_info,
                }
    return runs


def generate_signal_waveforms(sid: str, seed: int = 42) -> dict[str, Any]:
    """Extract acceleration signals, FFT spectrum, and packet drops for a scenario."""
    sc = make_scenario(sid, seed=seed)
    obs, vessel = generate_observations(sc)

    timestamps = [float(round(o.timestamp, 4)) for o in obs]
    ax = [float(round(o.acceleration[0], 4)) for o in obs]
    ay = [float(round(o.acceleration[1], 4)) for o in obs]
    az = [float(round(o.acceleration[2], 4)) for o in obs]
    packet_received = [bool(o.packet_received) for o in obs]

    raw_samples = [o.acceleration for o in obs]
    mags = [float(round(val, 4)) for val in acceleration_magnitude(raw_samples)]

    # FFT features using Subsea spectral_features
    usable_samples = [o.acceleration for o in obs if o.packet_received]
    features = spectral_features(usable_samples, sampling_rate=50.0) if usable_samples else {}

    # Compute continuous spectrum for plotting
    centered = np.asarray(mags) - np.mean(mags)
    spectrum = np.abs(np.fft.rfft(centered)) ** 2
    freqs = np.fft.rfftfreq(centered.size, 1.0 / 50.0)

    # Decimate spectrum if large for web transport
    if len(freqs) > 128:
        step = len(freqs) // 128
        freqs_plot = freqs[::step]
        spec_plot = spectrum[::step]
    else:
        freqs_plot = freqs
        spec_plot = spectrum

    return {
        "scenario_id": sid,
        "sample_count": len(obs),
        "sampling_rate_hz": 50.0,
        "timestamps": timestamps,
        "ax": ax,
        "ay": ay,
        "az": az,
        "magnitude": mags,
        "packet_received": packet_received,
        "packet_loss_count": sum(not p for p in packet_received),
        "spectral_features": {k: float(round(v, 4)) for k, v in features.items()},
        "frequency_bins": [float(round(f, 2)) for f in freqs_plot],
        "spectral_power": [float(round(p, 4)) for p in spec_plot],
    }


def generate_geometry_kinematics(sid: str, seed: int = 42) -> dict[str, Any]:
    """Generate 2D metric kinematics and cable interaction metrics."""
    cable_polyline = [(0.0, 0.0), (100.0, 0.0)]
    sc = make_scenario(sid, seed=seed)
    obs, vessel = generate_observations(sc)

    if vessel is None:
        return {
            "scenario_id": sid,
            "cable_polyline": [[p[0], p[1]] for p in cable_polyline],
            "vessel_trajectory": [],
            "trajectory_timestamps": [],
            "vessel_current_position": None,
            "speed": 0.0,
            "heading": 0.0,
            "position_uncertainty": 0.0,
            "reported": False,
            "closest_point_of_approach_m": None,
            "closest_point_timestamp": None,
            "dwell_time_within_10m_s": 0.0,
            "crossing_detected": False,
        }

    # Synthesize vessel approach track over 10 points
    t0 = vessel.timestamp - 10.0
    dt = 1.0
    trajectory: list[tuple[float, float]] = []
    track_times: list[float] = []

    for i in range(11):
        t = t0 + i * dt
        # Approach along heading towards vessel.position
        progress = i / 10.0
        rad = np.radians(vessel.heading)
        offset_dist = (1.0 - progress) * (vessel.speed * 10.0)
        px = vessel.position[0] - offset_dist * np.sin(rad)
        py = vessel.position[1] - offset_dist * np.cos(rad)
        trajectory.append((float(round(px, 2)), float(round(py, 2))))
        track_times.append(float(round(t, 2)))

    cpa_dist, cpa_idx = closest_point_of_approach(trajectory, cable_polyline)
    dwell = dwell_time(trajectory, track_times, cable_polyline, radius=10.0)
    crossing = crossing_detected(trajectory, cable_polyline)

    return {
        "scenario_id": sid,
        "cable_polyline": [[p[0], p[1]] for p in cable_polyline],
        "vessel_trajectory": [[p[0], p[1]] for p in trajectory],
        "trajectory_timestamps": track_times,
        "vessel_current_position": [float(round(vessel.position[0], 2)), float(round(vessel.position[1], 2))],
        "speed": float(round(vessel.speed, 2)),
        "heading": float(round(vessel.heading, 1)),
        "position_uncertainty": float(round(vessel.position_uncertainty, 2)),
        "reported": vessel.reported,
        "closest_point_of_approach_m": float(round(cpa_dist, 2)),
        "closest_point_timestamp": track_times[cpa_idx],
        "dwell_time_within_10m_s": float(round(dwell, 2)),
        "crossing_detected": bool(crossing),
    }


def generate_timelines(sid: str, seed: int = 42) -> dict[str, Any]:
    """Generate sliding-window timelines of CP, CA, R, U and decision states."""
    sc = make_scenario(sid, seed=seed)
    obs, vessel = generate_observations(sc)

    window_size = 64
    step = 16
    n_samples = len(obs)

    times = []
    cp_list = []
    ca_list = []
    r_list = []
    u_list = []
    decisions = []

    for start in range(0, max(1, n_samples - window_size + 1), step):
        sub_obs = obs[start : start + window_size]
        if not sub_obs:
            continue
        mid_t = sub_obs[-1].timestamp
        res = run_pipeline(sub_obs, vessel, environmental_event=sc.environmental_event, now=mid_t)
        times.append(float(round(mid_t, 3)))
        cp_list.append(float(round(res.physical_confidence, 4)))
        ca_list.append(float(round(res.association_confidence, 4)))
        r_list.append(float(round(res.reliability, 4)))
        u_list.append(float(round(res.uncertainty, 4)))
        decisions.append(res.decision.value)

    return {
        "scenario_id": sid,
        "window_size": window_size,
        "step_size": step,
        "timestamps": times,
        "physical_confidence": cp_list,
        "association_confidence": ca_list,
        "reliability": r_list,
        "uncertainty": u_list,
        "decisions": decisions,
    }
