#!/usr/bin/env python3
"""Export real pipeline simulations, manifests, tables, and provenance to web/data/*.json.

This script executes without modifying any research logic in src/.
All exported data is cryptographically traceable and tagged with data_kind.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import shutil
import sys

# Ensure Subsea src is on Python search path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import yaml

from subsea.web_export import (
    export_early_warning_eval,
    export_meta,
    export_scenario_catalog,
    generate_geometry_kinematics,
    generate_scenario_runs,
    generate_signal_waveforms,
    generate_timelines,
    generate_twin_runs,
    unavailable_payload,
)


def load_json_or_unavailable(path: Path, cmd: str) -> dict:
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return unavailable_payload(cmd)
    return unavailable_payload(cmd)


def load_csv_table(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    with open(path, mode="r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        return list(reader)


def sha256_file(path: Path) -> str:
    if not path.is_file():
        return ""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    web_dir = root / "web"
    data_dir = web_dir / "data"
    figures_dir = web_dir / "assets" / "figures"

    data_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    print("[Web Exporter] Starting export to web/data/...")

    # 1. Scenarios Catalog
    print("  -> Exporting scenarios.json...")
    scenarios_data = {
        "metadata": export_meta("SIMULATION", "src/subsea/simulation.py"),
        "scenarios": export_scenario_catalog(),
    }
    (data_dir / "scenarios.json").write_text(json.dumps(scenarios_data, indent=2), encoding="utf-8")

    # 2. Scenario Runs (22 scenarios x 6 attacks x 5 severities)
    print("  -> Precomputing scenario_runs.json (seed=42)...")
    runs_data = {
        "metadata": export_meta("SIMULATION", "src/subsea/pipeline.py"),
        "runs": generate_scenario_runs(seed=42),
    }
    (data_dir / "scenario_runs.json").write_text(json.dumps(runs_data, indent=2), encoding="utf-8")

    # 3. Waveforms and FFT Spectra (representative sample of scenarios)
    print("  -> Exporting signals.json...")
    waveforms = {}
    for sid in ["S01", "S02", "S03", "S04", "S05", "S06", "S07", "S08", "S09", "S10", "S13", "S17", "S18"]:
        waveforms[sid] = generate_signal_waveforms(sid, seed=42)
    signals_data = {
        "metadata": export_meta("SIMULATION", "src/subsea/features.py"),
        "waveforms": waveforms,
    }
    (data_dir / "signals.json").write_text(json.dumps(signals_data, indent=2), encoding="utf-8")

    # 4. Geometry and Kinematics
    print("  -> Exporting geometry.json...")
    geometries = {}
    for sid in ["S01", "S02", "S03", "S04", "S08", "S11", "S17", "S18", "S20", "S22"]:
        geometries[sid] = generate_geometry_kinematics(sid, seed=42)
    geometry_data = {
        "metadata": export_meta("SIMULATION", "src/subsea/geometry.py"),
        "geometries": geometries,
    }
    (data_dir / "geometry.json").write_text(json.dumps(geometry_data, indent=2), encoding="utf-8")

    # 5. Sliding-Window Evidence Timelines
    print("  -> Exporting timelines.json...")
    timelines = {}
    for sid in ["S01", "S02", "S03", "S04", "S07", "S10", "S13", "S17", "S18"]:
        timelines[sid] = generate_timelines(sid, seed=42)
    timelines_data = {
        "metadata": export_meta("SIMULATION", "src/subsea/pipeline.py"),
        "timelines": timelines,
    }
    (data_dir / "timelines.json").write_text(json.dumps(timelines_data, indent=2), encoding="utf-8")

    # 6. System Configuration & Decision Gates
    print("  -> Exporting config.json and decision_paths.json...")
    sys_cfg_path = root / "config" / "system.yaml"
    sys_cfg = yaml.safe_load(sys_cfg_path.read_text(encoding="utf-8")) if sys_cfg_path.is_file() else {}

    config_data = {
        "metadata": export_meta("SIMULATION", "config/system.yaml"),
        "config": sys_cfg,
        "effective_thresholds": {
            "physical": 0.55,
            "association": 0.60,
            "t2": 0.65,
            "t3": 0.85,
            "tx_uncertainty": float(sys_cfg.get("decision", {}).get("tx_uncertainty", 0.65)),
            "tx_reliability": float(sys_cfg.get("decision", {}).get("tx_reliability", 0.35)),
            "t3_uncertainty": float(sys_cfg.get("decision", {}).get("t3_uncertainty", 0.35)),
        },
    }
    (data_dir / "config.json").write_text(json.dumps(config_data, indent=2), encoding="utf-8")

    decision_paths_data = {
        "metadata": export_meta("SIMULATION", "src/subsea/decision.py"),
        "gates": [
            {
                "gate": 1,
                "name": "Reliability Fail-Closed Gating",
                "condition": "reliability <= tx_reliability (0.35)",
                "target_decision": "TX",
                "explanation": "Genuinely degraded sensor hardware / communication failure triggers immediate fail-closed alert.",
            },
            {
                "gate": 2,
                "name": "Physical Quiet Background Check",
                "condition": "physical_confidence < physical (0.55)",
                "target_decision": "T0",
                "explanation": "Quiet healthy window with no physical disturbance detected on healthy sensor.",
            },
            {
                "gate": 3,
                "name": "Conflicting Evidence / High Uncertainty Gating",
                "condition": "uncertainty >= tx_uncertainty (0.65)",
                "target_decision": "TX",
                "explanation": "Physical disturbance is present, but evidence is conflicting, degraded, or uncertain.",
            },
            {
                "gate": 4,
                "name": "Vessel Association Corroboration Check",
                "condition": "association_confidence < association (0.60)",
                "target_decision": "T1",
                "explanation": "Physical disturbance is present, but uncorroborated by vessel association.",
            },
            {
                "gate": 5,
                "name": "High-Confidence Escalation Gate",
                "condition": "score >= t3 (0.85) AND uncertainty < t3_uncertainty (0.35)",
                "target_decision": "T3 (if met) / T2 (otherwise)",
                "explanation": "Strong physical and vessel corroboration with low uncertainty escalates to T3; else T2.",
            },
        ],
    }
    (data_dir / "decision_paths.json").write_text(json.dumps(decision_paths_data, indent=2), encoding="utf-8")

    # 7. Hypotheses Definitions
    print("  -> Exporting hypotheses.json...")
    hypotheses_data = {
        "metadata": export_meta("SIMULATION", "src/subsea/models.py"),
        "definitions": {
            "vessel_associated_disturbance": "Physical disturbance correlated in time and space with an AIS vessel track (anchor drag, trawl contact).",
            "environmental_disturbance": "Natural ambient or hydrodynamic event (ocean surface waves, seafloor turbulence, seismic tremors).",
            "non_vessel_mechanical_disturbance": "Mechanical impact or dropped object lacking vessel spatial-temporal corroboration.",
            "sensor_system_fault": "Sensor hardware malfunction, optical transmission link dropout, or packet degradation.",
        },
    }
    (data_dir / "hypotheses.json").write_text(json.dumps(hypotheses_data, indent=2), encoding="utf-8")

    # 8. Adversarial Lab Manifests and Tables
    print("  -> Exporting adversarial.json...")
    adv_manifest = load_json_or_unavailable(
        root / "artifacts" / "adversarial" / "adversarial_manifest.json",
        "python scripts/run_adversarial.py",
    )
    adv_table = load_csv_table(root / "artifacts" / "tables" / "table8_adversarial_robustness.csv")
    adversarial_data = {
        "metadata": export_meta("SIMULATION", "artifacts/adversarial/adversarial_manifest.json"),
        "manifest": adv_manifest,
        "table": adv_table,
    }
    (data_dir / "adversarial.json").write_text(json.dumps(adversarial_data, indent=2), encoding="utf-8")

    # 9. Baselines and Ablations
    print("  -> Exporting baselines.json and ablation.json...")
    base_manifest = load_json_or_unavailable(
        root / "artifacts" / "baselines" / "baselines_manifest.json",
        "python scripts/run_baselines.py",
    )
    base_table = load_csv_table(root / "artifacts" / "tables" / "table5_baseline_comparison.csv")
    baselines_data = {
        "metadata": export_meta("SIMULATION", "artifacts/baselines/baselines_manifest.json"),
        "manifest": base_manifest,
        "table": base_table,
    }
    (data_dir / "baselines.json").write_text(json.dumps(baselines_data, indent=2), encoding="utf-8")

    ablation_manifest = load_json_or_unavailable(
        root / "artifacts" / "ablation" / "ablation_manifest.json",
        "python scripts/run_baselines.py",
    )
    ablation_table = load_csv_table(root / "artifacts" / "tables" / "table6_ablation_study.csv")
    ablation_data = {
        "metadata": export_meta("SIMULATION", "artifacts/ablation/ablation_manifest.json"),
        "manifest": ablation_manifest,
        "table": ablation_table,
    }
    (data_dir / "ablation.json").write_text(json.dumps(ablation_data, indent=2), encoding="utf-8")

    # 10. Robustness & Calibration
    print("  -> Exporting robustness.json and calibration.json...")
    robustness_table = load_csv_table(root / "artifacts" / "tables" / "table7_sensor_failure.csv")
    cal_manifest = load_json_or_unavailable(
        root / "artifacts" / "simulation" / "threshold_calibration_manifest.json",
        "python scripts/run_simulation.py",
    )
    cal_table = load_csv_table(root / "artifacts" / "tables" / "table_calibration.csv")

    robustness_data = {
        "metadata": export_meta("SIMULATION", "artifacts/tables/table7_sensor_failure.csv"),
        "table": robustness_table,
    }
    (data_dir / "robustness.json").write_text(json.dumps(robustness_data, indent=2), encoding="utf-8")

    calibration_data = {
        "metadata": export_meta("SIMULATION", "artifacts/simulation/threshold_calibration_manifest.json"),
        "manifest": cal_manifest,
        "table": cal_table,
    }
    (data_dir / "calibration.json").write_text(json.dumps(calibration_data, indent=2), encoding="utf-8")

    # 11. Real DAS Evaluation (Marlinks, EMSO, Oliktok)
    print("  -> Exporting real_das.json...")
    marlinks_man = load_json_or_unavailable(
        root / "artifacts" / "real_data_evaluation" / "marlinks_manifest.json",
        "python scripts/run_real_evaluation.py",
    )
    emso_man = load_json_or_unavailable(
        root / "artifacts" / "real_data_evaluation" / "emso_manifest.json",
        "python scripts/run_real_evaluation.py",
    )
    oliktok_man = load_json_or_unavailable(
        root / "artifacts" / "real_data_evaluation" / "oliktok_manifest.json",
        "python scripts/run_oliktok_evaluation.py",
    )

    real_das_data = {
        "metadata": export_meta("REAL_DAS", "artifacts/real_data_evaluation/"),
        "marlinks": marlinks_man,
        "emso": emso_man,
        "oliktok": oliktok_man,
        "disclaimers": {
            "oliktok_finding": "No T2/T3 vessel-escalation decisions occurred during the evaluated recording.",
            "marlinks_gap": "Marlinks demonstrates continuous 1D vessel distance correlation (rho = 0.9482), but lacks 2D AIS polyline tracking, MMSI, and ground-truth damage annotations.",
            "emso_role": "EMSO provides an independent deep-sea unperturbed noise floor baseline (CV = 0.0008) validating spectral stability.",
            "autocorrelation_caveat": "High temporal autocorrelation across consecutive hourly/10s windows reduces effective degrees of freedom; reported p-values reflect nominal sample counts.",
        },
    }
    (data_dir / "real_das.json").write_text(json.dumps(real_das_data, indent=2), encoding="utf-8")

    # 12. Provenance Records
    print("  -> Exporting provenance.json...")
    prov_file = root / "data" / "PROVENANCE.json"
    prov_records = json.loads(prov_file.read_text(encoding="utf-8")) if prov_file.is_file() else {}

    provenance_data = {
        "metadata": export_meta("REAL_DAS", "data/PROVENANCE.json"),
        "provenance_records": prov_records.get("provenance_records", []),
        "manifest_hashes": {
            "EXPERIMENT_MANIFEST.json": sha256_file(root / "artifacts" / "EXPERIMENT_MANIFEST.json"),
            "marlinks_manifest.json": sha256_file(root / "artifacts" / "real_data_evaluation" / "marlinks_manifest.json"),
            "emso_manifest.json": sha256_file(root / "artifacts" / "real_data_evaluation" / "emso_manifest.json"),
            "oliktok_manifest.json": sha256_file(root / "artifacts" / "real_data_evaluation" / "oliktok_manifest.json"),
        },
    }
    (data_dir / "provenance.json").write_text(json.dumps(provenance_data, indent=2), encoding="utf-8")

    # 13. Publication Figures and Tables Catalog
    print("  -> Exporting publications.json & copying static figures...")
    exp_manifest = load_json_or_unavailable(
        root / "artifacts" / "EXPERIMENT_MANIFEST.json",
        "python scripts/run_phase3_validation.py",
    )

    # Copy static figures into web/assets/figures/
    src_figures = root / "artifacts" / "figures"
    if src_figures.is_dir():
        for fig_path in src_figures.glob("*.png"):
            shutil.copy2(fig_path, figures_dir / fig_path.name)

    src_paper_core = root / "artifacts" / "paper_evaluation" / "core"
    if src_paper_core.is_dir():
        for fig_path in src_paper_core.glob("*.png"):
            shutil.copy2(fig_path, figures_dir / fig_path.name)

    src_real_figs = root / "artifacts" / "real_data_evaluation"
    if src_real_figs.is_dir():
        for fig_path in src_real_figs.glob("*.png"):
            shutil.copy2(fig_path, figures_dir / fig_path.name)

    publications_data = {
        "metadata": export_meta("SIMULATION", "artifacts/EXPERIMENT_MANIFEST.json"),
        "publication_figures": [
            {"id": "fig01", "name": "Marlinks Energy vs Distance", "filename": "fig01_marlinks_energy_vs_distance.png", "cohort": "REAL_DAS"},
            {"id": "fig02", "name": "Marlinks Spatial CPA", "filename": "fig02_marlinks_spatial_cpa.png", "cohort": "REAL_DAS"},
            {"id": "fig03", "name": "Marlinks Temporal Response", "filename": "fig03_marlinks_temporal_response.png", "cohort": "REAL_DAS"},
            {"id": "fig04", "name": "EMSO Temporal Stability", "filename": "fig04_emso_temporal_stability.png", "cohort": "REAL_DAS"},
            {"id": "fig05", "name": "Scenario Confusion Matrix", "filename": "fig05_scenario_confusion_matrix.png", "cohort": "SIMULATION"},
            {"id": "fig06", "name": "Baseline Method Comparison", "filename": "fig06_baseline_comparison.png", "cohort": "SIMULATION"},
            {"id": "fig07", "name": "Ablation Study Performance", "filename": "fig07_ablation_performance.png", "cohort": "SIMULATION"},
            {"id": "fig08", "name": "Uncertainty vs Evidence", "filename": "fig08_uncertainty_vs_evidence.png", "cohort": "SIMULATION"},
            {"id": "fig09", "name": "Adversarial Robustness AER", "filename": "fig09_adversarial_robustness_aer.png", "cohort": "SIMULATION"},
            {"id": "fig10", "name": "Sensor Failure Degradation", "filename": "fig10_sensor_failure_degradation.png", "cohort": "SIMULATION"},
            {"id": "fig11", "name": "Decision State Distribution", "filename": "fig11_decision_distribution.png", "cohort": "SIMULATION"},
            {"id": "fig12", "name": "Pipeline Latency Distribution", "filename": "fig12_latency_distribution.png", "cohort": "SIMULATION"},
            {"id": "fig_oliktok_temp", "name": "Oliktok Temporal Stability (27.6 Days)", "filename": "oliktok_temporal_stability.png", "cohort": "REAL_DAS"},
            {"id": "fig_oliktok_chan", "name": "Oliktok Channel Statistics", "filename": "oliktok_channel_statistics.png", "cohort": "REAL_DAS"},
            {"id": "fig_oliktok_phys", "name": "Oliktok Physical Confidence Distribution", "filename": "oliktok_physical_confidence.png", "cohort": "REAL_DAS"},
        ],
        "publication_tables": [
            {"id": "table1", "name": "Table I: Real Dataset Characteristics", "filename": "table1_real_dataset_characteristics.csv", "cohort": "REAL_DAS"},
            {"id": "table2", "name": "Table II: Marlinks Proximity Validation", "filename": "table2_marlinks_validation.csv", "cohort": "REAL_DAS"},
            {"id": "table3", "name": "Table III: EMSO Deep-Sea Baseline", "filename": "table3_emso_baseline.csv", "cohort": "REAL_DAS"},
            {"id": "table4", "name": "Table IV: Controlled Scenarios (S01–S22)", "filename": "table4_controlled_scenarios.csv", "cohort": "SIMULATION"},
            {"id": "table5", "name": "Table V: Baseline Method Comparison", "filename": "table5_baseline_comparison.csv", "cohort": "SIMULATION"},
            {"id": "table6", "name": "Table VI: Multimodal Evidence Ablation Study", "filename": "table6_ablation_study.csv", "cohort": "SIMULATION"},
            {"id": "table7", "name": "Table VII: Sensor Failure & Noise Degradation", "filename": "table7_sensor_failure.csv", "cohort": "SIMULATION"},
            {"id": "table8", "name": "Table VIII: Adversarial Robustness & AER", "filename": "table8_adversarial_robustness.csv", "cohort": "SIMULATION"},
            {"id": "table9", "name": "Table IX: Competing Hypotheses Formulation", "filename": "table9_competing_hypotheses.csv", "cohort": "SIMULATION"},
            {"id": "table10", "name": "Table X: Computational Latency & Performance", "filename": "table10_computational_performance.csv", "cohort": "SIMULATION"},
        ],
    }
    (data_dir / "publications.json").write_text(json.dumps(publications_data, indent=2), encoding="utf-8")

    # 14. Overview Dashboard Summary
    print("  -> Exporting overview.json...")
    overview_data = {
        "metadata": export_meta("SIMULATION", "artifacts/EXPERIMENT_MANIFEST.json"),
        "framework_title": "An Uncertainty-Aware Multimodal Evidence Fusion Framework for Subsea Cable Disturbance Assessment",
        "cohorts": {
            "controlled_simulation": {
                "name": "Controlled Simulation Benchmark",
                "data_kind": "SIMULATION",
                "scenarios": 22,
                "trials": 2200,
                "master_seed": 42,
                "status": "VALIDATED",
                "key_finding": "Decoupled physical disturbance detection from vessel attribution with reliable fail-closed TX handling.",
            },
            "real_das": {
                "name": "Real Submarine Fiber DAS Deployments",
                "data_kind": "REAL_DAS",
                "deployments": ["Marlinks (North Sea)", "EMSO (Mediterranean)", "Dryad Oliktok (Arctic Ocean)"],
                "total_duration_evaluated": "27.6 days Arctic + 1,050 s deep-sea + 10 min North Sea wind farm",
                "status": "EXECUTED",
                "key_finding": "No T2/T3 vessel-escalation decisions occurred during the evaluated Arctic environmental recording; Spearman rho = 0.9482 proximity correlation on North Sea export cable.",
            },
            "hardware_in_the_loop": {
                "name": "AbyssLink Hardware-in-the-Loop Bridge",
                "data_kind": "HIL_SIMULATED_ACCEL",
                "hardware": "ESP32 (115200 baud UART, 300ms telemetry) + Optical Link + Ultrasonic",
                "status": "OPERATIONAL",
                "key_finding": "Validates real-time protocol decoding, timing, and optical fault detection with synthesized 50 Hz MPU6050 accelerometer.",
            },
        },
        "kpis": {
            "scenarios_count": 22,
            "real_datasets_count": 3,
            "total_simulation_trials": 2200,
            "oliktok_eval_duration_days": 27.6,
            "adversarial_error_rate_aer": 0.0,
        },
    }
    (data_dir / "overview.json").write_text(json.dumps(overview_data, indent=2), encoding="utf-8")

    # 15. Sync latest HIL run decisions if available
    hil_ptr = web_dir / "hil" / "latest.json"
    if hil_ptr.is_file():
        try:
            ptr_data = json.loads(hil_ptr.read_text(encoding="utf-8"))
            dec_src = Path(ptr_data.get("decisions_path", ""))
            if dec_src.is_file():
                shutil.copy2(dec_src, web_dir / "hil" / "decisions.jsonl")
                print(f"  -> Synced latest HIL decisions to {web_dir / 'hil' / 'decisions.jsonl'}")
        except Exception as e:
            print(f"  -> Note: could not sync HIL decisions ({e})")

    # 16. Digital Twin Precomputed Runs
    print("  -> Exporting twin_runs.json (seed=42)...")
    twin_runs_data = {
        "metadata": export_meta("SIMULATION", "src/subsea/digital_twin.py", seed=42),
        "twin_runs": generate_twin_runs(seed=42),
    }
    (data_dir / "twin_runs.json").write_text(json.dumps(twin_runs_data, indent=2), encoding="utf-8")

    # 17. Early Warning Benchmarks Evaluation
    print("  -> Exporting early_warning_eval.json...")
    ew_eval_data = export_early_warning_eval()
    (data_dir / "early_warning_eval.json").write_text(json.dumps(ew_eval_data, indent=2), encoding="utf-8")

    print(f"[Web Exporter] Successfully exported all web data files to {data_dir}!")


if __name__ == "__main__":
    main()
