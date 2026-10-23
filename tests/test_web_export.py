"""Tests for web data exporter and extraction helpers."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from subsea.simulation import _DEFINITIONS
from subsea.web_export import (
    export_meta,
    export_scenario_catalog,
    generate_geometry_kinematics,
    generate_scenario_runs,
    generate_signal_waveforms,
    generate_timelines,
    unavailable_payload,
)


def test_unavailable_payload():
    """Verify missing source contract."""
    res = unavailable_payload("python scripts/generate.py")
    assert res["status"] == "unavailable"
    assert res["how_to_generate"] == "python scripts/generate.py"


def test_export_meta_tags():
    """Verify metadata tags and data_kind tagging."""
    meta = export_meta("SIMULATION", "test/path", seed=42)
    assert meta["software_version"] == "0.1.0"
    assert meta["data_kind"] == "SIMULATION"
    assert meta["source_manifest_path"] == "test/path"
    assert meta["seed"] == 42
    assert "exported_at" in meta


def test_scenario_catalog_integrity():
    """Verify all 22 scenarios match _DEFINITIONS from simulation.py."""
    catalog = export_scenario_catalog()
    assert len(catalog) == 22
    for sc in catalog:
        sid = sc["scenario_id"]
        assert sid in _DEFINITIONS
        assert sc["description"] == _DEFINITIONS[sid][0]
        assert sc["vessel_present"] == _DEFINITIONS[sid][1]
        assert sc["disturbance_present"] == _DEFINITIONS[sid][2]


def test_scenario_runs_precomputation_determinism():
    """Verify precomputed runs for S01 and S04 with seed 42."""
    runs = generate_scenario_runs(seed=42)
    assert len(runs) == 22

    # S01 (Normal) with no attack
    s01_clean = runs["S01"]["none"]["0.0"]
    assert s01_clean["result"]["decision"] == "T0"
    assert s01_clean["vessel"] is None

    # S04 (Anchor dragging) with no attack
    s04_clean = runs["S04"]["none"]["0.0"]
    assert s04_clean["result"]["decision"] in {"T2", "T3"}
    assert s04_clean["vessel"] is not None
    assert s04_clean["vessel"]["distance_to_cable_m"] <= 10.0

    # S04 with severe AIS spoofing
    s04_spoofed = runs["S04"]["ais_spoofing"]["1.0"]
    # Under spoofing, vessel is displaced far away, decision must not be T2/T3
    assert s04_spoofed["result"]["decision"] in {"T1", "TX"}
    assert s04_spoofed["vessel"]["distance_to_cable_m"] > 10.0


def test_signals_waveforms_and_fft():
    """Verify triaxial waveforms, magnitude, and FFT features."""
    signals = generate_signal_waveforms("S04", seed=42)
    assert signals["sample_count"] == 256
    assert signals["sampling_rate_hz"] == 50.0
    assert len(signals["ax"]) == 256
    assert len(signals["magnitude"]) == 256
    assert len(signals["frequency_bins"]) > 0
    assert "dominant_frequency" in signals["spectral_features"]
    assert "rms" in signals["spectral_features"]


def test_geometry_and_kinematics():
    """Verify geometry CPA, dwell time, and crossing calculations."""
    geo = generate_geometry_kinematics("S04", seed=42)
    assert geo["scenario_id"] == "S04"
    assert len(geo["cable_polyline"]) == 2
    assert len(geo["vessel_trajectory"]) == 11
    assert geo["closest_point_of_approach_m"] is not None
    assert geo["closest_point_of_approach_m"] >= 0.0

    # Non-vessel scenario should have empty trajectory
    geo_quiet = generate_geometry_kinematics("S01", seed=42)
    assert geo_quiet["vessel_current_position"] is None
    assert len(geo_quiet["vessel_trajectory"]) == 0


def test_timelines_sliding_window():
    """Verify sliding-window timelines generation."""
    tl = generate_timelines("S04", seed=42)
    assert len(tl["timestamps"]) > 0
    assert len(tl["physical_confidence"]) == len(tl["timestamps"])
    assert len(tl["decisions"]) == len(tl["timestamps"])
    assert all(d in {"T0", "T1", "T2", "T3", "TX"} for d in tl["decisions"])


def test_exported_json_files_exist():
    """Verify all 14 expected JSON files exist in web/data/."""
    root = Path(__file__).resolve().parent.parent
    data_dir = root / "web" / "data"

    expected_files = [
        "scenarios.json",
        "scenario_runs.json",
        "signals.json",
        "geometry.json",
        "timelines.json",
        "config.json",
        "decision_paths.json",
        "hypotheses.json",
        "adversarial.json",
        "baselines.json",
        "ablation.json",
        "robustness.json",
        "calibration.json",
        "real_das.json",
        "provenance.json",
        "publications.json",
        "overview.json",
        "twin_runs.json",
        "early_warning_eval.json",
    ]
    for fname in expected_files:
        fpath = data_dir / fname
        assert fpath.is_file(), f"Missing exported web data file: {fname}"

        # Verify valid JSON
        data = json.loads(fpath.read_text(encoding="utf-8"))
        assert "metadata" in data
        assert "data_kind" in data["metadata"]


def test_twin_runs_precomputation_determinism():
    """Verify precomputed twin runs for all scenarios with seed 42."""
    from subsea.web_export import generate_twin_runs

    runs1 = generate_twin_runs(seed=42)
    runs2 = generate_twin_runs(seed=42)

    expected_scenarios = {
        "normal_operation",
        "approaching_vessel",
        "low_level_vibration",
        "increasing_disturbance",
        "severe_disturbance",
        "sensor_degradation",
        "recovery",
    }
    assert set(runs1.keys()) == expected_scenarios

    for scen_id in expected_scenarios:
        scen1 = runs1[scen_id]
        scen2 = runs2[scen_id]
        assert scen1["scenario_id"] == scen_id
        assert scen1["seed"] == 42
        assert len(scen1["steps"]) > 0
        assert len(scen1["steps"]) == len(scen2["steps"])

        # Check determinism on initial and mid steps
        s1 = scen1["steps"][0]
        s2 = scen2["steps"][0]
        assert s1["early_warning"]["state"] == s2["early_warning"]["state"]
        assert s1["twin_heuristic_state"] == s2["twin_heuristic_state"]
        assert s1["twin_heuristic_label"] == "Twin heuristic (NOT the fusion classifier)"

    # Approaching vessel must have t_event ~ 15.9s
    assert runs1["approaching_vessel"]["t_event"] == 15.9
    # Sensor degradation must trip to WX
    wx_steps = [s for s in runs1["sensor_degradation"]["steps"] if s["early_warning"]["state"] == "WX"]
    assert len(wx_steps) > 0


def test_early_warning_eval_structure():
    """Verify early warning evaluation scorecard and metrics structure."""
    from subsea.web_export import export_early_warning_eval

    res = export_early_warning_eval()
    assert res["status"] == "AVAILABLE"
    assert res["metadata"]["data_kind"] == "SIMULATION"
    assert len(res["scorecard"]) == 7
    assert "latency_distributions" in res
    assert "operational_metrics" in res
    assert "baseline_ablation_comparison" in res
    assert "operating_curve" in res
    assert res["operational_metrics"]["false_alarms_per_hour"] == 0.0

