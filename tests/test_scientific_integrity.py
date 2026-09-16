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


def test_correct_confusion_matrix_f1():
    """Verify that reported competing-hypotheses macro F1 matches the underlying confusion matrix."""
    root = Path(__file__).resolve().parent.parent
    hyp_p = root / "artifacts" / "simulation" / "competing_hypotheses_manifest.json"
    assert hyp_p.is_file(), "Competing hypotheses manifest must exist"
    data = json.loads(hyp_p.read_text(encoding="utf-8"))

    cm = data["confusion_matrix"]
    classes = list(cm.keys())
    f1_list = []
    total_samples = 0
    weighted_f1_sum = 0.0

    for h in classes:
        tp = cm[h][h]
        fp = sum(cm[other][h] for other in classes if other != h)
        fn = sum(cm[h][other] for other in classes if other != h)
        support = sum(cm[h].values())
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        f1_list.append(f1)
        total_samples += support
        weighted_f1_sum += f1 * support

        assert data["per_class_metrics"][h]["precision"] == pytest.approx(prec, abs=1e-4)
        assert data["per_class_metrics"][h]["recall"] == pytest.approx(rec, abs=1e-4)
        assert data["per_class_metrics"][h]["f1"] == pytest.approx(f1, abs=1e-4)
        assert data["per_class_metrics"][h]["true_count"] == support

    macro_f1 = sum(f1_list) / len(f1_list)
    weighted_f1 = weighted_f1_sum / total_samples

    assert data["macro_f1"] == pytest.approx(macro_f1, abs=1e-4)
    assert data["weighted_f1"] == pytest.approx(weighted_f1, abs=1e-4)
    # Ensure macro F1 is ~0.6808, NOT 0.9329
    assert data["macro_f1"] == pytest.approx(0.6808, abs=1e-3)
    assert data["macro_f1"] < 0.75, "Macro F1 must reflect true H3 zero-score, not inflated"


def test_consistent_tx_denominator():
    """Verify that TX rate explicitly specifies its denominator N=2200 for trial-level reporting."""
    root = Path(__file__).resolve().parent.parent
    base_p = root / "artifacts" / "baselines" / "baselines_manifest.json"
    sim_p = root / "artifacts" / "simulation" / "scenario_matrix.json"
    
    base_data = json.loads(base_p.read_text(encoding="utf-8"))
    sim_data = json.loads(sim_p.read_text(encoding="utf-8"))

    total_trials = len(sim_data["trials"])
    assert total_trials == 2200

    prop_tx_count = sum(t["decision"] == "TX" for t in sim_data["trials"])
    assert prop_tx_count == 300

    expected_trial_tx_rate = 300 / 2200
    assert base_data["metrics"]["proposed"]["tx_rate"] == pytest.approx(expected_trial_tx_rate, abs=1e-4)
    assert base_data["metrics"]["proposed"]["total_evaluations"] == 2200
    # Must NOT equal the old misreported 0.3182
    assert base_data["metrics"]["proposed"]["tx_rate"] != pytest.approx(0.3182, abs=1e-3)


def test_no_copied_or_hardcoded_baseline_metrics():
    """Verify weighted fusion baseline has distinct logic from proposed and is not copied."""
    root = Path(__file__).resolve().parent.parent
    base_p = root / "artifacts" / "baselines" / "baselines_manifest.json"
    base_data = json.loads(base_p.read_text(encoding="utf-8"))

    prop = base_data["metrics"]["proposed"]
    weighted = base_data["metrics"]["weighted"]

    # Weighted baseline has no health/uncertainty gating, so TX rate must be 0
    assert weighted["tx_rate"] == 0.0
    assert prop["tx_rate"] > 0.10

    # Decision recall and accuracy must differ between proposed and weighted
    assert weighted["recall"] != prop["recall"]
    assert weighted["f1"] != prop["f1"]

    # Statistical test between proposed and weighted must exist and not be a dummy copy
    stat_test = base_data["statistical_tests_vs_proposed"]["weighted"]
    assert "paired_bootstrap" in stat_test
    assert stat_test["paired_bootstrap"]["p_value"] < 0.05 or stat_test["observed_difference"] != 0.0


def test_ablation_switches_disable_intended_components():
    """Verify that each ablation switch actually modifies the specific evidence components."""
    from subsea.baselines import evaluate_method
    from subsea.models import Scenario
    from subsea.pipeline import run_pipeline
    from subsea.simulation import make_scenario, generate_observations

    sc = make_scenario("S04", seed=42)
    obs, vessel = generate_observations(sc)
    res = run_pipeline(obs, vessel)

    # A: physical_only
    rec_a = evaluate_method("physical_only", res, sc)
    assert rec_a["inputs"]["effective_decision_inputs"]["association_confidence"] == 0.0
    assert rec_a["inputs"]["effective_decision_inputs"]["uncertainty"] == 0.0
    assert rec_a["inputs"]["effective_decision_inputs"]["reliability"] == 1.0

    # without_uncertainty
    rec_u = evaluate_method("without_uncertainty", res, sc)
    assert rec_u["inputs"]["effective_decision_inputs"]["uncertainty"] == 0.0
    assert rec_u["changed_components"] == ("uncertainty",)

    # without_health
    rec_h = evaluate_method("without_health", res, sc)
    assert rec_h["inputs"]["effective_decision_inputs"]["reliability"] == 1.0
    assert "health" in rec_h["changed_components"]

    # weighted
    rec_w = evaluate_method("weighted", res, sc)
    assert rec_w["inputs"]["effective_decision_inputs"]["uncertainty"] == 0.0
    assert rec_w["inputs"]["effective_decision_inputs"]["reliability"] == 1.0


def test_aer_independent_calculation():
    """Verify AER calculation adheres to N(T0 despite true H1) / N(trials)."""
    root = Path(__file__).resolve().parent.parent
    adv_p = root / "artifacts" / "adversarial" / "adversarial_manifest.json"
    adv_data = json.loads(adv_p.read_text(encoding="utf-8"))

    assert "scientific_statement" in adv_data
    assert "Within the implemented vessel-side attack model" in adv_data["scientific_statement"]
    assert "perfect robustness" not in adv_data["scientific_statement"].lower()

    for r in adv_data["results"]:
        assert r["AER"] == r["t0_count"] / r["trials"]
        assert r["AER"] == 0.0
        assert r["t0_count"] == 0
        assert sum([r["t0_count"], r["t1_count"], r["t2_count"], r["t3_count"], r["tx_count"]]) == r["trials"]


def test_brier_ece_metadata_completeness():
    """Verify calibration manifest contains explicit metadata defining targets and probability variables."""
    root = Path(__file__).resolve().parent.parent
    cal_p = root / "artifacts" / "simulation" / "threshold_calibration_manifest.json"
    cal_data = json.loads(cal_p.read_text(encoding="utf-8"))

    meta = cal_data["metric_metadata"]
    assert "target_definition" in meta
    assert "primary_probability_definition" in meta
    assert meta["number_of_observations"] == 2200
    assert "brier_score_formula" in meta
    assert "primary_hypothesis_calibration" in cal_data
    assert "fused_score_calibration" in cal_data
    assert "sensor_reliability_diagnostics" in cal_data


def test_figure_table_manifest_consistency():
    """Verify result_consistency_report has zero inconsistent values across all artifacts."""
    root = Path(__file__).resolve().parent.parent
    rep_p = root / "artifacts" / "audit" / "result_consistency_report.json"
    assert rep_p.is_file(), "Consistency report must exist"

    rep = json.loads(rep_p.read_text(encoding="utf-8"))
    assert rep["inconsistent_count"] == 0
    assert rep["total_checks"] >= 50
    assert all(r["consistent"] for r in rep["audit_records"])


def test_no_unsupported_telemetry_budget_claim():
    """Verify that no unsupported 40x telemetry budget claims exist in project files."""
    root = Path(__file__).resolve().parent.parent
    
    # Check in code, scripts, manifests, and tables
    for check_dir in ["src", "scripts", "artifacts/tables", "artifacts/performance"]:
        dir_p = root / check_dir
        if not dir_p.exists():
            continue
        for f in dir_p.glob("*.*"):
            if f.suffix in {".py", ".csv", ".tex", ".json"}:
                text = f.read_text(encoding="utf-8", errors="ignore")
                assert "40x" not in text, f"Found unsupported 40x claim in {f}"
                assert "40X" not in text, f"Found unsupported 40X claim in {f}"

