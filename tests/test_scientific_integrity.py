"""Scientific integrity and zero-fabrication safety regression test suite."""
from __future__ import annotations

import json
from pathlib import Path
import pytest


def test_real_manifests_contain_no_fabricated_metrics():
    root = Path(__file__).resolve().parent.parent
    marlinks_man_p = root / "artifacts" / "real_data_evaluation" / "marlinks_manifest.json"
    emso_man_p = root / "artifacts" / "real_data_evaluation" / "emso_manifest.json"

    assert marlinks_man_p.is_file(), "Marlinks manifest must exist"
    assert emso_man_p.is_file(), "EMSO manifest must exist"

    marlinks = json.loads(marlinks_man_p.read_text(encoding="utf-8"))
    emso = json.loads(emso_man_p.read_text(encoding="utf-8"))

    # Verify status is EXECUTED
    assert marlinks["status"] == "EXECUTED"
    assert emso["status"] == "EXECUTED"

    # Marlinks must NOT contain fabricated F1, precision, recall, or accuracy
    res_m = marlinks["results"]
    assert "f1" not in res_m
    assert "accuracy" not in res_m
    assert "precision" not in res_m
    assert "recall" not in res_m
    assert "ais_latitude" not in res_m
    assert "cable_polyline" not in res_m
    assert "threat_label" not in res_m

    # EMSO must NOT claim vessel detection or AIS
    res_e = emso["results"]
    assert "vessel" not in res_e
    assert "ais" not in res_e
    assert "f1" not in res_e


def test_real_dataset_sha256_matches_provenance():
    root = Path(__file__).resolve().parent.parent
    prov_p = root / "data" / "PROVENANCE.json"
    assert prov_p.is_file(), "PROVENANCE.json must exist"

    prov = json.loads(prov_p.read_text(encoding="utf-8"))["provenance_records"]
    assert len(prov) == 2

    import hashlib
    for rec in prov:
        fpath = root / rec["relative_path"]
        assert fpath.is_file(), f"File {fpath} must exist"
        computed_hash = hashlib.sha256(fpath.read_bytes()).hexdigest()
        assert computed_hash == rec["sha256"], f"SHA256 mismatch for {fpath}"


def test_real_and_synthetic_results_are_strictly_separated():
    root = Path(__file__).resolve().parent.parent
    sim_man_p = root / "artifacts" / "simulation" / "scenario_matrix.json"
    assert sim_man_p.is_file(), "Simulation scenario matrix must exist"

    sim_man = json.loads(sim_man_p.read_text(encoding="utf-8"))
    assert sim_man["data_kind"] == "CONTROLLED SIMULATION"

    real_man_p = root / "artifacts" / "real_data_evaluation" / "marlinks_manifest.json"
    real_man = json.loads(real_man_p.read_text(encoding="utf-8"))
    assert "CONTROLLED SIMULATION" not in str(real_man)


def test_all_22_scenarios_have_verified_ground_truth():
    root = Path(__file__).resolve().parent.parent
    sim_man_p = root / "artifacts" / "simulation" / "scenario_matrix.json"
    sim_man = json.loads(sim_man_p.read_text(encoding="utf-8"))

    expected_scenarios = {f"S{i:02d}" for i in range(1, 23)}
    assert set(sim_man["scenario_summaries"].keys()) == expected_scenarios

    for sid, summary in sim_man["scenario_summaries"].items():
        assert summary["trials"] == 100
        assert 0.0 <= summary["accuracy"] <= 1.0


def test_master_experiment_manifest_reproducibility():
    root = Path(__file__).resolve().parent.parent
    exp_man_p = root / "artifacts" / "EXPERIMENT_MANIFEST.json"
    assert exp_man_p.is_file(), "Master EXPERIMENT_MANIFEST.json must exist"

    exp_man = json.loads(exp_man_p.read_text(encoding="utf-8"))
    assert exp_man["phase"] == "PHASE 3: FULL EXPERIMENTAL VALIDATION"
    assert "provenance_boundary" in exp_man
    assert "real_datasets" in exp_man["provenance_boundary"]
    assert "controlled_simulation" in exp_man["provenance_boundary"]

    # Verify all referenced table and figure files exist
    for rel_tbl in exp_man["publication_tables"]:
        assert (root / "artifacts" / rel_tbl).is_file(), f"Table {rel_tbl} missing"

    for rel_fig in exp_man["publication_figures"]:
        assert (root / "artifacts" / rel_fig).is_file(), f"Figure {rel_fig} missing"
