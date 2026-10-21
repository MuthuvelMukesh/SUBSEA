"""Automated Tests for Subsea Cable Digital Twin Simulation Module.

Verifies:
- All 7 scenario implementations
- Deterministic reproducibility for identical random seeds
- Output divergence across distinct seeds
- Immutable data provenance tags (DataSource.SIMULATED)
- Frame data structures, types, and JSON serialization
"""

from __future__ import annotations

import pytest

from subsea.digital_twin import DigitalTwinFrame, DigitalTwinSimulator, TwinScenario
from subsea.provenance_quality import DataQuality, DataSource, SensorReading


def test_all_seven_scenarios_instantiate_and_step():
    """Verifies that all 7 scenarios execute and advance state successfully."""
    sim = DigitalTwinSimulator(seed=123)

    for scen in TwinScenario:
        sim.set_scenario(scen)
        assert sim.current_scenario == scen
        assert sim.elapsed_s == 0.0

        frame = sim.step(dt=0.3)
        assert isinstance(frame, DigitalTwinFrame)
        assert frame.scenario_id == scen.value
        assert frame.elapsed_s == pytest.approx(0.3, rel=1e-3)
        assert len(frame.readings) == 5

        # Verify all channels are present
        expected_channels = {
            "das_rms",
            "vessel_distance",
            "seafloor_temperature",
            "cable_strain",
            "cable_health_index",
        }
        assert set(frame.readings.keys()) == expected_channels

        # Verify provenance is strictly SIMULATED
        for ch_name, reading in frame.readings.items():
            assert isinstance(reading, SensorReading)
            assert reading.source == DataSource.SIMULATED
            assert reading.scenario_id == scen.value


def test_deterministic_seed_reproducibility():
    """Identical random seeds must produce identical numerical values across all frames."""
    sim1 = DigitalTwinSimulator(seed=42)
    sim2 = DigitalTwinSimulator(seed=42)

    sim1.set_scenario(TwinScenario.INCREASING_DISTURBANCE, seed=42)
    sim2.set_scenario(TwinScenario.INCREASING_DISTURBANCE, seed=42)

    for _ in range(30):
        f1 = sim1.step(dt=0.3)
        f2 = sim2.step(dt=0.3)

        assert f1.elapsed_s == f2.elapsed_s
        assert f1.phase == f2.phase
        assert f1.summary["vibration_rms"] == f2.summary["vibration_rms"]
        assert f1.summary["distance_m"] == f2.summary["distance_m"]
        assert f1.summary["strain_microstrain"] == f2.summary["strain_microstrain"]
        assert f1.summary["temperature_c"] == f2.summary["temperature_c"]
        assert f1.summary["condition_index"] == f2.summary["condition_index"]


def test_divergence_across_different_seeds():
    """Distinct random seeds must produce divergent noise trajectories."""
    sim1 = DigitalTwinSimulator(seed=101)
    sim2 = DigitalTwinSimulator(seed=999)

    sim1.set_scenario(TwinScenario.NORMAL_OPERATION, seed=101)
    sim2.set_scenario(TwinScenario.NORMAL_OPERATION, seed=999)

    rms_diffs = []
    for _ in range(20):
        f1 = sim1.step(dt=0.3)
        f2 = sim2.step(dt=0.3)
        rms_diffs.append(abs(f1.summary["vibration_rms"] - f2.summary["vibration_rms"]))

    # At least some frames must differ due to independent RNG draws
    assert max(rms_diffs) > 0.0


def test_generate_scenario_series_length():
    """generate_scenario must produce the correct number of frames for requested duration."""
    sim = DigitalTwinSimulator(seed=42)
    duration_s = 15.0
    dt = 0.3
    expected_frames = int(round(duration_s / dt))

    frames = sim.generate_scenario(TwinScenario.APPROACHING_VESSEL, duration_s=duration_s, dt=dt, seed=42)
    assert len(frames) == expected_frames
    assert frames[0].elapsed_s == pytest.approx(0.3, rel=1e-3)
    assert frames[-1].elapsed_s == pytest.approx(duration_s, rel=1e-3)


def test_frame_serialization_to_dict():
    """DigitalTwinFrame.to_dict must produce valid JSON-serializable primitives."""
    sim = DigitalTwinSimulator(seed=42)
    frame = sim.step(dt=0.3)
    data = frame.to_dict()

    assert data["scenario_id"] == "normal_operation"
    assert data["elapsed_s"] == 0.3
    assert "readings" in data
    assert "summary" in data

    for ch_name, r_dict in data["readings"].items():
        assert r_dict["source"] == "SIMULATED"
        assert "value" in r_dict
        assert "unit" in r_dict
        assert "quality" in r_dict


def test_sensor_degradation_scenario_transitions():
    """Sensor degradation scenario must degrade quality and trigger missing/stale markers."""
    sim = DigitalTwinSimulator(seed=42)
    sim.set_scenario(TwinScenario.SENSOR_DEGRADATION, seed=42)

    qualities_seen = set()
    # Step for 16 seconds (54 steps * 0.3s)
    for _ in range(54):
        frame = sim.step(dt=0.3)
        for r in frame.readings.values():
            qualities_seen.add(r.quality)

    # Must observe both DEGRADED and STALE or MISSING
    assert DataQuality.DEGRADED in qualities_seen
    assert DataQuality.STALE in qualities_seen or DataQuality.MISSING in qualities_seen
