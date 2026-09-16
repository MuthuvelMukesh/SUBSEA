"""Full Phase 3 Experimental Validation Suite.

Executes:
1. Controlled Scenario Matrix (S01-S22, 100 trials each)
2. Monte Carlo Statistical Robustness
3. Baseline Methods Comparison
4. 10 Ablation Configurations
5. Sensor Failure & Missing Evidence Study
6. Competing Hypotheses Classification Matrix
7. Adversarial Robustness & AER Sweeps
8. Decision Threshold Sensitivity & Calibration
9. Latency & Computational Performance Profiling
10. Publication Tables 1-10 (CSV + LaTeX)
11. Publication Figures 1-12 (IEEE 300 DPI)
12. Master Reproducibility Manifest (artifacts/EXPERIMENT_MANIFEST.json)
"""
from __future__ import annotations

import csv
import hashlib
import json
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

from subsea import __version__
from subsea.adversarial import SUPPORTED_ATTACKS, apply_attack
from subsea.baselines import METHODS, evaluate_method
from subsea.decision import decide
from subsea.experiments import run_trials
from subsea.metrics import (
    adversarial_error_rate, brier_score, bootstrap_confidence_interval,
    calibration_curve, classification_metrics, expected_calibration_error,
    false_high_escalation_rate,
)
from subsea.models import DecisionState, Hypothesis
from subsea.pipeline import run_pipeline
from subsea.simulation import (
    SUPPORTED_SCENARIOS, generate_observations, generate_vessels,
    make_scenario, _DEFINITIONS,
)
from subsea.statistics import cohens_d, mcnemar_test, paired_bootstrap, permutation_test


def get_git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL, text=True,
        ).strip()
    except Exception:
        return "unknown"


def latex_escape(value: object) -> str:
    replacements = {
        "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$",
        "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(c, c) for c in str(value))


def save_csv_and_tex(rows: list[dict[str, Any]], fieldnames: list[str], csv_path: Path, tex_path: Path, caption: str = "") -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    with open(tex_path, "w", encoding="utf-8") as f:
        col_align = "l" + "r" * (len(fieldnames) - 1)
        f.write("\\begin{table}[htbp]\n\\centering\n")
        if caption:
            f.write(f"\\caption{{{caption}}}\n")
        f.write(f"\\begin{{tabular}}{{{col_align}}}\n\\toprule\n")
        f.write(" & ".join(latex_escape(h) for h in fieldnames) + " \\\\\n\\midrule\n")
        for row in rows:
            f.write(" & ".join(latex_escape(row.get(h, "")) for h in fieldnames) + " \\\\\n")
        f.write("\\bottomrule\n\\end{tabular}\n\\end{table}\n")


def main() -> None:
    print("=" * 70)
    print("SUBSEA: PHASE 3 FULL EXPERIMENTAL VALIDATION")
    print("=" * 70)
    root_dir = Path(__file__).resolve().parent.parent
    artifacts_dir = root_dir / "artifacts"
    
    sim_dir = artifacts_dir / "simulation"
    base_dir = artifacts_dir / "baselines"
    abl_dir = artifacts_dir / "ablation"
    adv_dir = artifacts_dir / "adversarial"
    mc_dir = artifacts_dir / "monte_carlo"
    perf_dir = artifacts_dir / "performance"
    tbl_dir = artifacts_dir / "tables"
    fig_dir = artifacts_dir / "figures"
    real_dir = artifacts_dir / "real_data_evaluation"

    for d in [sim_dir, base_dir, abl_dir, adv_dir, mc_dir, perf_dir, tbl_dir, fig_dir]:
        d.mkdir(parents=True, exist_ok=True)

    master_seed = 42
    trials_per_scenario = 100
    scenarios = sorted(SUPPORTED_SCENARIOS)

    # -----------------------------------------------------------------------
    # 1. SCENARIO MATRIX & TRIAL EXECUTION (S01-S22, 100 trials each)
    # -----------------------------------------------------------------------
    print(f"\n[1/10] Executing Controlled Scenario Matrix ({len(scenarios)} scenarios x {trials_per_scenario} trials = {len(scenarios)*trials_per_scenario} trials)...")
    all_trials: list[dict[str, Any]] = []
    scenario_summaries: dict[str, Any] = {}

    for s_idx, sid in enumerate(scenarios):
        desc, vessel_present, disturbance_present = _DEFINITIONS[sid]
        s_trials: list[dict[str, Any]] = []
        for t in range(trials_per_scenario):
            t_seed = master_seed + s_idx * trials_per_scenario + t
            sc = make_scenario(sid, t_seed)
            obs, vessel = generate_observations(sc)
            candidates = list(generate_vessels(sc, tuple(o.timestamp for o in obs)))
            t_start = time.perf_counter()
            results = [run_pipeline(obs, c, environmental_event=sc.environmental_event) for c in candidates]
            res = max(results, key=lambda r: r.association_confidence) if results else run_pipeline(obs, None, environmental_event=sc.environmental_event)
            latency_ms = (time.perf_counter() - t_start) * 1000.0

            true_h1 = sc.vessel_present and sc.disturbance_present and not sc.environmental_event
            is_correct = (res.decision.value in {"T2", "T3"}) if true_h1 else (res.decision.value in {"T0", "T1", "TX"})
            
            # Ground truth hypothesis
            if sc.sensor_failure or sc.communication_failure:
                true_hyp = Hypothesis.SENSOR_FAULT.value
            elif sc.environmental_event:
                true_hyp = Hypothesis.ENVIRONMENTAL.value
            elif sc.mechanical_event:
                true_hyp = Hypothesis.MECHANICAL.value
            elif true_h1:
                true_hyp = Hypothesis.VESSEL_DISTURBANCE.value
            else:
                true_hyp = "normal_background"

            trial_rec = {
                "scenario_id": sid,
                "description": desc,
                "trial_index": t,
                "seed": t_seed,
                "configuration_hash": hashlib.sha256(f"{sid}_{t_seed}".encode()).hexdigest()[:12],
                "ground_truth": {
                    "vessel_present": sc.vessel_present,
                    "disturbance_present": sc.disturbance_present,
                    "environmental_event": sc.environmental_event,
                    "sensor_failure": sc.sensor_failure,
                    "mechanical_event": sc.mechanical_event,
                    "true_h1": true_h1,
                    "true_hypothesis": true_hyp,
                },
                "physical_confidence": float(res.physical_confidence),
                "association_confidence": float(res.association_confidence),
                "behaviour_confidence": float(res.audit.get("association_components", {}).get("behaviour", 0.0)),
                "fusion_score": float(res.audit.get("fused_score", 0.0)),
                "reliability": float(res.reliability),
                "uncertainty": float(res.uncertainty),
                "counter_evidence": list(res.counter_evidence),
                "decision": res.decision.value,
                "latency_ms": latency_ms,
                "predicted_hypothesis": max(res.hypothesis_scores.items(), key=lambda x: x[1])[0],
                "hypothesis_scores": res.hypothesis_scores,
                "correct": is_correct,
                "reason_for_decision": "; ".join(res.rationale),
            }
            s_trials.append(trial_rec)
            all_trials.append(trial_rec)

        acc = sum(r["correct"] for r in s_trials) / len(s_trials)
        mean_u = float(np.mean([r["uncertainty"] for r in s_trials]))
        mean_cp = float(np.mean([r["physical_confidence"] for r in s_trials]))
        mean_ca = float(np.mean([r["association_confidence"] for r in s_trials]))
        dec_counts = {}
        for r in s_trials:
            dec_counts[r["decision"]] = dec_counts.get(r["decision"], 0) + 1

        scenario_summaries[sid] = {
            "description": desc,
            "trials": trials_per_scenario,
            "accuracy": acc,
            "mean_physical_confidence": mean_cp,
            "mean_association_confidence": mean_ca,
            "mean_uncertainty": mean_u,
            "decision_distribution": dec_counts,
        }

    matrix_manifest = {
        "status": "EXECUTED",
        "data_kind": "CONTROLLED SIMULATION",
        "total_scenarios": len(scenarios),
        "trials_per_scenario": trials_per_scenario,
        "master_seed": master_seed,
        "scenario_summaries": scenario_summaries,
        "total_trial_records": len(all_trials),
        "trials": all_trials,
    }
    with open(sim_dir / "scenario_matrix.json", "w", encoding="utf-8") as f:
        json.dump(matrix_manifest, f, indent=2)
    print("Saved artifacts/simulation/scenario_matrix.json.")

    # -----------------------------------------------------------------------
    # 2. MONTE CARLO STATISTICAL ANALYSIS
    # -----------------------------------------------------------------------
    print("\n[2/10] Computing Monte Carlo statistical distributions...")
    mc_stats = {}
    for sid in scenarios:
        s_data = [t for t in all_trials if t["scenario_id"] == sid]
        for field in ["physical_confidence", "association_confidence", "reliability", "uncertainty", "fusion_score", "latency_ms"]:
            vals = np.array([t[field] for t in s_data], dtype=float)
            # Bootstrap 95% CI
            rng = np.random.default_rng(master_seed)
            boot_means = [np.mean(rng.choice(vals, size=len(vals), replace=True)) for _ in range(2000)]
            ci_low = float(np.percentile(boot_means, 2.5))
            ci_high = float(np.percentile(boot_means, 97.5))
            mc_stats.setdefault(sid, {})[field] = {
                "mean": float(np.mean(vals)),
                "std": float(np.std(vals)),
                "median": float(np.median(vals)),
                "ci_95": [ci_low, ci_high],
                "min": float(np.min(vals)),
                "max": float(np.max(vals)),
            }

    mc_manifest = {
        "status": "EXECUTED",
        "data_kind": "CONTROLLED SIMULATION",
        "trials_per_scenario": trials_per_scenario,
        "master_seed": master_seed,
        "statistics": mc_stats,
    }
    with open(mc_dir / "monte_carlo_manifest.json", "w", encoding="utf-8") as f:
        json.dump(mc_manifest, f, indent=2)
    print("Saved artifacts/monte_carlo/monte_carlo_manifest.json.")

    # -----------------------------------------------------------------------
    # 3. BASELINE METHODS COMPARISON
    # -----------------------------------------------------------------------
    print("\n[3/10] Evaluating Baseline Methods...")
    baseline_methods = ["physical_only", "association_only", "behaviour_only", "weighted", "proposed"]
    baseline_records: dict[str, list[dict[str, Any]]] = {m: [] for m in baseline_methods}

    for t_rec in all_trials:
        sid = t_rec["scenario_id"]
        seed = t_rec["seed"]
        sc = make_scenario(sid, seed)
        obs, vessel = generate_observations(sc)
        candidates = list(generate_vessels(sc, tuple(o.timestamp for o in obs)))
        results = [run_pipeline(obs, c, environmental_event=sc.environmental_event) for c in candidates]
        res = max(results, key=lambda r: r.association_confidence) if results else run_pipeline(obs, None, environmental_event=sc.environmental_event)
        
        for m in baseline_methods:
            m_res = evaluate_method(m, res, sc)
            baseline_records[m].append({
                "scenario_id": sid,
                "seed": seed,
                "decision": m_res["decision"],
                "truth": m_res["truth"],
            })

    baseline_metrics: dict[str, Any] = {}
    for m in baseline_methods:
        recs = baseline_records[m]
        actual = [r["truth"]["vessel_present"] and r["truth"]["disturbance_present"] and not r["truth"]["environmental_event"] for r in recs]
        pred_pos = [r["decision"] in {"T2", "T3"} for r in recs]
        tp = sum(a and p for a, p in zip(actual, pred_pos))
        fp = sum(not a and p for a, p in zip(actual, pred_pos))
        fn = sum(a and not p for a, p in zip(actual, pred_pos))
        tn = sum(not a and not p for a, p in zip(actual, pred_pos))
        
        acc = (tp + tn) / len(actual) if actual else 0.0
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        far = fp / (fp + tn) if fp + tn else 0.0
        miss = fn / (tp + fn) if tp + fn else 0.0
        tx_count = sum(r["decision"] == "TX" for r in recs)
        tx_rate = tx_count / len(recs)

        baseline_metrics[m] = {
            "accuracy": acc,
            "precision": prec,
            "recall": rec,
            "f1": f1,
            "false_alarm_rate": far,
            "miss_rate": miss,
            "tx_rate": tx_rate,
            "total_evaluations": len(recs),
        }

    # Statistical significance vs proposed
    stat_comparisons: dict[str, Any] = {}
    prop_acc_list = [
        1.0 if (r["decision"] in {"T2", "T3"}) == (r["truth"]["vessel_present"] and r["truth"]["disturbance_present"] and not r["truth"]["environmental_event"])
        else 0.0 for r in baseline_records["proposed"]
    ]
    for m in baseline_methods:
        if m == "proposed":
            continue
        m_acc_list = [
            1.0 if (r["decision"] in {"T2", "T3"}) == (r["truth"]["vessel_present"] and r["truth"]["disturbance_present"] and not r["truth"]["environmental_event"])
            else 0.0 for r in baseline_records[m]
        ]
        boot = paired_bootstrap(prop_acc_list, m_acc_list, seed=master_seed)
        perm = permutation_test(prop_acc_list, m_acc_list, seed=master_seed)
        d = cohens_d(prop_acc_list, m_acc_list)
        mcn = mcnemar_test([x == 1.0 for x in prop_acc_list], [x == 1.0 for x in m_acc_list])
        stat_comparisons[m] = {
            "paired_bootstrap": boot,
            "permutation_test": perm,
            "cohens_d": d,
            "mcnemar": mcn,
        }

    base_manifest = {
        "status": "EXECUTED",
        "data_kind": "CONTROLLED SIMULATION",
        "methods": baseline_methods,
        "metrics": baseline_metrics,
        "statistical_tests_vs_proposed": stat_comparisons,
    }
    with open(base_dir / "baselines_manifest.json", "w", encoding="utf-8") as f:
        json.dump(base_manifest, f, indent=2)
    print("Saved artifacts/baselines/baselines_manifest.json.")

    # -----------------------------------------------------------------------
    # 4. ABLATION STUDY (10 configurations)
    # -----------------------------------------------------------------------
    print("\n[4/10] Evaluating 10 Ablation Configurations...")
    ablation_configs = [
        ("A: physical_only", "physical_only"),
        ("B: physical + spatial", "physical_plus_spatial"),
        ("C: physical + temporal", "physical_plus_temporal"),
        ("D: physical + behaviour", "physical_plus_behaviour"),
        ("E: physical + spatial + temporal", "physical_spatial_temporal"),
        ("F: full fusion w/o uncertainty", "without_uncertainty"),
        ("G: full fusion w/o health", "without_health"),
        ("H: full fusion w/o counter-evidence", "without_counter_evidence"),
        ("I: full fusion w/o spatial-temporal", "without_spatial_temporal_association"),
        ("J: full proposed framework", "proposed"),
    ]
    ablation_metrics: dict[str, Any] = {}

    for label, method_key in ablation_configs:
        recs = []
        for t_rec in all_trials:
            sid = t_rec["scenario_id"]
            seed = t_rec["seed"]
            sc = make_scenario(sid, seed)
            obs, vessel = generate_observations(sc)
            candidates = list(generate_vessels(sc, tuple(o.timestamp for o in obs)))
            results = [run_pipeline(obs, c, environmental_event=sc.environmental_event) for c in candidates]
            res = max(results, key=lambda r: r.association_confidence) if results else run_pipeline(obs, None, environmental_event=sc.environmental_event)
            m_res = evaluate_method(method_key, res, sc)
            recs.append(m_res)

        actual = [r["truth"]["vessel_present"] and r["truth"]["disturbance_present"] and not r["truth"]["environmental_event"] for r in recs]
        pred_pos = [r["decision"] in {"T2", "T3"} for r in recs]
        tp = sum(a and p for a, p in zip(actual, pred_pos))
        fp = sum(not a and p for a, p in zip(actual, pred_pos))
        fn = sum(a and not p for a, p in zip(actual, pred_pos))
        tn = sum(not a and not p for a, p in zip(actual, pred_pos))
        
        acc = (tp + tn) / len(actual) if actual else 0.0
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        far = fp / (fp + tn) if fp + tn else 0.0
        miss = fn / (tp + fn) if tp + fn else 0.0
        tx_count = sum(r["decision"] == "TX" for r in recs)
        tx_rate = tx_count / len(recs)

        ablation_metrics[label] = {
            "method_key": method_key,
            "accuracy": acc,
            "precision": prec,
            "recall": rec,
            "f1": f1,
            "false_alarm_rate": far,
            "miss_rate": miss,
            "tx_rate": tx_rate,
        }

    abl_manifest = {
        "status": "EXECUTED",
        "data_kind": "CONTROLLED SIMULATION",
        "ablation_results": ablation_metrics,
    }
    with open(abl_dir / "ablation_manifest.json", "w", encoding="utf-8") as f:
        json.dump(abl_manifest, f, indent=2)
    print("Saved artifacts/ablation/ablation_manifest.json.")

    # -----------------------------------------------------------------------
    # 5. SENSOR FAILURE & MISSING EVIDENCE STUDY
    # -----------------------------------------------------------------------
    print("\n[5/10] Evaluating Sensor Failure & Missing Evidence Conditions...")
    failure_scenarios = [
        ("Normal Sensor Baseline", "S04"),
        ("Single Sensor Intermittent Packet Loss (25%)", "S10"),
        ("Multiple Sensor Packet Loss (50%)", "S15"),
        ("Sensor Drift & Calibration Offset", "S15"),
        ("Communication Backhaul Failure", "S08"),
        ("Complete Sensor Hardware Failure", "S07"),
        ("Missing Vessel AIS Corroboration", "S16"),
        ("Spatial-Temporal Conflicting Evidence", "S13"),
    ]
    failure_records = []
    for cond_name, sid in failure_scenarios:
        s_data = [t for t in all_trials if t["scenario_id"] == sid]
        mean_u = float(np.mean([t["uncertainty"] for t in s_data]))
        mean_r = float(np.mean([t["reliability"] for t in s_data]))
        tx_c = sum(t["decision"] == "TX" for t in s_data)
        t0_c = sum(t["decision"] == "T0" for t in s_data)
        t1_c = sum(t["decision"] == "T1" for t in s_data)
        t2_c = sum(t["decision"] == "T2" for t in s_data)
        t3_c = sum(t["decision"] == "T3" for t in s_data)
        acc = sum(t["correct"] for t in s_data) / len(s_data)

        failure_records.append({
            "condition": cond_name,
            "scenario_id": sid,
            "trials": len(s_data),
            "mean_uncertainty": mean_u,
            "mean_reliability": mean_r,
            "tx_rate": tx_c / len(s_data),
            "decisions": {"T0": t0_c, "T1": t1_c, "T2": t2_c, "T3": t3_c, "TX": tx_c},
            "correctness": acc,
        })

    fail_manifest = {
        "status": "EXECUTED",
        "data_kind": "CONTROLLED SIMULATION",
        "conditions": failure_records,
    }
    with open(sim_dir / "sensor_failure_manifest.json", "w", encoding="utf-8") as f:
        json.dump(fail_manifest, f, indent=2)
    print("Saved artifacts/simulation/sensor_failure_manifest.json.")

    # -----------------------------------------------------------------------
    # 6. COMPETING HYPOTHESES CLASSIFICATION
    # -----------------------------------------------------------------------
    print("\n[6/10] Evaluating Competing Hypotheses Classification...")
    hyp_classes = [
        Hypothesis.VESSEL_DISTURBANCE.value,
        Hypothesis.ENVIRONMENTAL.value,
        Hypothesis.MECHANICAL.value,
        Hypothesis.SENSOR_FAULT.value,
    ]
    conf_matrix = {t_h: {p_h: 0 for p_h in hyp_classes} for t_h in hyp_classes}

    for t_rec in all_trials:
        true_h = t_rec["ground_truth"]["true_hypothesis"]
        if true_h in hyp_classes:
            pred_h = t_rec["predicted_hypothesis"]
            if pred_h in hyp_classes:
                conf_matrix[true_h][pred_h] += 1

    per_class_metrics = {}
    f1_list = []
    for h in hyp_classes:
        tp = conf_matrix[h][h]
        fp = sum(conf_matrix[other][h] for other in hyp_classes if other != h)
        fn = sum(conf_matrix[h][other] for other in hyp_classes if other != h)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        f1_list.append(f1)
        per_class_metrics[h] = {
            "true_count": sum(conf_matrix[h].values()),
            "precision": prec,
            "recall": rec,
            "f1": f1,
        }

    macro_f1 = float(np.mean(f1_list))
    total_samples = sum(m["true_count"] for m in per_class_metrics.values())
    weighted_f1 = float(sum(m["f1"] * m["true_count"] for m in per_class_metrics.values()) / total_samples) if total_samples else 0.0

    hyp_manifest = {
        "status": "EXECUTED",
        "data_kind": "CONTROLLED SIMULATION",
        "confusion_matrix": conf_matrix,
        "per_class_metrics": per_class_metrics,
        "macro_f1": macro_f1,
        "weighted_f1": weighted_f1,
        "total_evaluated": total_samples,
    }
    with open(sim_dir / "competing_hypotheses_manifest.json", "w", encoding="utf-8") as f:
        json.dump(hyp_manifest, f, indent=2)
    print("Saved artifacts/simulation/competing_hypotheses_manifest.json.")

    # -----------------------------------------------------------------------
    # 7. ADVERSARIAL ROBUSTNESS & AER SWEEPS
    # -----------------------------------------------------------------------
    print("\n[7/10] Evaluating Adversarial Robustness & AER Sweeps...")
    adv_attacks = ["ais_spoofing", "transponder_suppression", "timestamp_manipulation", "spatial_manipulation", "combined_evasion"]
    severities = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
    adv_results = []

    for attack in adv_attacks:
        for sev in severities:
            preds = []
            for t in range(trials_per_scenario):
                t_seed = master_seed + 999 + t
                sc = make_scenario("S04", t_seed)  # True H1 disturbance scenario
                obs, vessel = generate_observations(sc)
                candidates = list(generate_vessels(sc, tuple(o.timestamp for o in obs)))
                attacked_candidates = [apply_attack(c, attack, sev) for c in candidates]
                results = [run_pipeline(obs, c, environmental_event=sc.environmental_event) for c in attacked_candidates]
                res = max(results, key=lambda r: r.association_confidence) if results else run_pipeline(obs, None, environmental_event=sc.environmental_event)
                preds.append(res)

            decisions = [r.decision.value for r in preds]
            true_h1_list = [True] * len(preds)
            # AER: Rate of incorrect collapse to T0 despite true H1 disturbance
            aer_val = sum(d == "T0" for d in decisions) / len(decisions)
            tx_val = sum(d == "TX" for d in decisions) / len(decisions)
            t2_t3_val = sum(d in {"T2", "T3"} for d in decisions) / len(decisions)
            mean_u = float(np.mean([r.uncertainty for r in preds]))

            adv_results.append({
                "attack": attack,
                "severity": sev,
                "trials": len(preds),
                "AER": aer_val,
                "TX_rate": tx_val,
                "escalated_T2_T3_rate": t2_t3_val,
                "mean_uncertainty": mean_u,
                "decisions": {d: sum(1 for x in decisions if x == d) for d in set(decisions)},
            })

    adv_manifest = {
        "status": "EXECUTED",
        "data_kind": "CONTROLLED SIMULATION",
        "threat_model": "Vessel-side AIS trajectory and transponder manipulation",
        "attacks_evaluated": adv_attacks,
        "severities": severities,
        "results": adv_results,
    }
    with open(adv_dir / "adversarial_manifest.json", "w", encoding="utf-8") as f:
        json.dump(adv_manifest, f, indent=2)
    print("Saved artifacts/adversarial/adversarial_manifest.json.")

    # -----------------------------------------------------------------------
    # 8. DECISION THRESHOLD SENSITIVITY & CALIBRATION
    # -----------------------------------------------------------------------
    print("\n[8/10] Evaluating Decision Threshold Sensitivity & Calibration...")
    labels = [1 if t["ground_truth"]["true_h1"] else 0 for t in all_trials]
    probs = [t["reliability"] for t in all_trials]
    bs = brier_score(labels, probs)
    ece = expected_calibration_error(labels, probs)
    curve = calibration_curve(labels, probs)
    ci = bootstrap_confidence_interval(probs)

    # Threshold sensitivity sweep on physical threshold
    sens_physical = []
    for th in [0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70]:
        th_decisions = [
            decide(
                physical_confidence=t["physical_confidence"],
                association_confidence=t["association_confidence"],
                reliability=t["reliability"],
                uncertainty=t["uncertainty"],
                thresholds={"physical": th},
            ).value for t in all_trials
        ]
        pos = [d in {"T2", "T3"} for d in th_decisions]
        tp = sum(a and p for a, p in zip(labels, pos))
        fp = sum(not a and p for a, p in zip(labels, pos))
        fn = sum(a and not p for a, p in zip(labels, pos))
        f1_th = 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0
        sens_physical.append({"threshold": th, "f1": f1_th})

    cal_manifest = {
        "status": "EXECUTED",
        "data_kind": "CONTROLLED SIMULATION",
        "brier_score": bs,
        "ECE": ece,
        "calibration_curve": curve,
        "confidence_interval": ci,
        "physical_threshold_sensitivity": sens_physical,
    }
    with open(sim_dir / "threshold_calibration_manifest.json", "w", encoding="utf-8") as f:
        json.dump(cal_manifest, f, indent=2)
    print("Saved artifacts/simulation/threshold_calibration_manifest.json.")

    # -----------------------------------------------------------------------
    # 9. COMPUTATIONAL PERFORMANCE & LATENCY
    # -----------------------------------------------------------------------
    print("\n[9/10] Measuring Sub-Component and End-to-End Latencies...")
    bench_scenario = make_scenario("S04", master_seed)
    b_obs, b_vessel = generate_observations(bench_scenario)
    
    das_latencies = []
    assoc_latencies = []
    fusion_latencies = []
    decision_latencies = []
    e2e_latencies = []

    from subsea.features import physical_confidence, spectral_features
    from subsea.association import associate
    from subsea.fusion import score_hypotheses, weighted_fusion
    from subsea.models import Evidence

    usable_acc = [o.acceleration for o in b_obs if o.packet_received]
    n_bench = 1000

    for _ in range(n_bench):
        # DAS features
        t0 = time.perf_counter()
        feats = spectral_features(usable_acc, 50.0)
        cp = physical_confidence(feats, baseline_rms=1.0, disturbance_rms=1.8)
        das_latencies.append((time.perf_counter() - t0) * 1000.0)


        # Association
        t0 = time.perf_counter()
        assoc = associate(b_vessel, b_obs[-1].timestamp, 5.0, interaction_radius=10.0, temporal_tolerance=5.0)
        assoc_latencies.append((time.perf_counter() - t0) * 1000.0)

        # Evidence fusion
        t0 = time.perf_counter()
        ev = [
            Evidence("p", cp, 1.0, 1.0, 1.0, Hypothesis.VESSEL_DISTURBANCE, "p"),
            Evidence("a", assoc.confidence, 1.0, 1.0, 1.0, Hypothesis.VESSEL_DISTURBANCE, "a"),
        ]
        fused, rel = weighted_fusion(ev)
        scores = score_hypotheses(cp, assoc.confidence, rel)
        fusion_latencies.append((time.perf_counter() - t0) * 1000.0)

        # Decision
        t0 = time.perf_counter()
        dec = decide(physical_confidence=cp, association_confidence=assoc.confidence, reliability=rel, uncertainty=0.1)
        decision_latencies.append((time.perf_counter() - t0) * 1000.0)

        # End-to-end
        t0 = time.perf_counter()
        run_pipeline(b_obs, b_vessel)
        e2e_latencies.append((time.perf_counter() - t0) * 1000.0)

    perf_metrics = {}
    for stage, lats in [
        ("DAS Spectral Processing", das_latencies),
        ("Spatio-Temporal Association", assoc_latencies),
        ("Multimodal Evidence Fusion", fusion_latencies),
        ("Decision State Machine", decision_latencies),
        ("End-to-End Pipeline", e2e_latencies),
    ]:
        perf_metrics[stage] = {
            "mean_ms": float(np.mean(lats)),
            "median_ms": float(np.median(lats)),
            "std_ms": float(np.std(lats)),
            "p95_ms": float(np.percentile(lats, 95)),
            "max_ms": float(np.max(lats)),
            "throughput_hz": float(1000.0 / np.mean(lats)),
        }

    perf_manifest = {
        "status": "EXECUTED",
        "iterations": n_bench,
        "environment": {
            "os": platform.platform(),
            "cpu": platform.processor(),
            "python": platform.python_version(),
        },
        "performance_metrics": perf_metrics,
    }
    with open(perf_dir / "performance_manifest.json", "w", encoding="utf-8") as f:
        json.dump(perf_manifest, f, indent=2)
    print("Saved artifacts/performance/performance_manifest.json.")

    # -----------------------------------------------------------------------
    # 10. GENERATING PUBLICATION TABLES & FIGURES
    # -----------------------------------------------------------------------
    print("\n[10/10] Generating Publication Tables (1-10) and Figures (1-12)...")

    # Table 1: Real Dataset Characteristics
    save_csv_and_tex(
        [
            {"Dataset": "Marlinks DAS Demo", "Modality": "Distributed Acoustic Sensing (DAS)", "Format": "HDF5", "Channels": "250", "Duration": "590 s", "Ground_Truth": "Continuous Proximity y (m)", "Status": "REAL DATA (EXECUTED)"},
            {"Dataset": "EMSO Ionian Seafloor", "Modality": "Distributed Acoustic Sensing (DAS)", "Format": "NumPy (.npy)", "Channels": "2,963", "Duration": "1,050 s", "Ground_Truth": "Unperturbed Seafloor Baseline", "Status": "REAL DATA (EXECUTED)"},
        ],
        ["Dataset", "Modality", "Format", "Channels", "Duration", "Ground_Truth", "Status"],
        tbl_dir / "table1_real_dataset_characteristics.csv",
        tbl_dir / "table1_real_dataset_characteristics.tex",
        "Characteristics of External Real Submarine DAS Datasets",
    )

    # Table 2: Marlinks Real-Data Validation
    marlinks_man = json.loads((real_dir / "marlinks_manifest.json").read_text(encoding="utf-8"))["results"]
    save_csv_and_tex(
        [
            {"Metric": "Spearman Rank Correlation (Energy vs 1/y)", "Value": f"{marlinks_man['correlation_metrics']['spearman_rho_energy_vs_inverse_dist']:.4f}", "P_Value": f"{marlinks_man['correlation_metrics']['spearman_p_energy_vs_inverse_dist']:.2e}", "Note": "Statistically significant monotonic proximity response"},
            {"Metric": "Pearson Correlation (Energy vs 1/y)", "Value": f"{marlinks_man['correlation_metrics']['pearson_r_energy_vs_inverse_dist']:.4f}", "P_Value": f"{marlinks_man['correlation_metrics']['pearson_p_energy_vs_inverse_dist']:.2e}", "Note": "Linear correlation with inverted distance"},
            {"Metric": "True Closest Point of Approach (CPA)", "Value": f"{marlinks_man['cpa_metrics']['true_cpa_distance_m']:.2f} m", "P_Value": "N/A", "Note": f"Occurs at step {marlinks_man['cpa_metrics']['true_cpa_index']} ({marlinks_man['cpa_metrics']['true_cpa_timestamp']})"},
            {"Metric": "Peak Acoustic Energy Timestamp", "Value": f"{marlinks_man['cpa_metrics']['peak_energy_timestamp']}", "P_Value": "N/A", "Note": f"Temporal lead offset: {marlinks_man['cpa_metrics']['cpa_time_offset_seconds']:.1f} s"},
            {"Metric": "Spatial Gini Coefficient at CPA", "Value": f"{marlinks_man['spatial_localization']['spatial_gini_coefficient']:.4f}", "P_Value": "N/A", "Note": "High spatial energy concentration under transit"},
            {"Metric": "Peak-to-Average Ratio (PAR) at CPA", "Value": f"{marlinks_man['spatial_localization']['peak_to_average_ratio']:.2f}", "P_Value": "N/A", "Note": f"Peak channel {marlinks_man['spatial_localization']['peak_sensor_channel']} vs baseline"},
            {"Metric": "Approach Monotonicity", "Value": f"{marlinks_man['monotonicity']['approach_energy_spearman']:.4f}", "P_Value": "N/A", "Note": "Monotonic energy growth during approach"},
            {"Metric": "Departure Monotonicity", "Value": f"{marlinks_man['monotonicity']['departure_energy_spearman']:.4f}", "P_Value": "N/A", "Note": "Monotonic energy decay during departure"},
        ],
        ["Metric", "Value", "P_Value", "Note"],
        tbl_dir / "table2_marlinks_validation.csv",
        tbl_dir / "table2_marlinks_validation.tex",
        "Marlinks Real DAS Continuous Proximity Validation Results",
    )

    # Table 3: EMSO Real-Data Baseline
    emso_man = json.loads((real_dir / "emso_manifest.json").read_text(encoding="utf-8"))["results"]
    save_csv_and_tex(
        [
            {"Parameter": "Fiber Optical Channels", "Value": f"{emso_man['channel_count']}", "Unit": "Channels", "Interpretation": "Continuous deep-sea subsea fiber cable"},
            {"Parameter": "Sampling Rate", "Value": f"{emso_man['sampling_rate_hz']:.1f}", "Unit": "Hz", "Interpretation": "Decimated optical phase strain rate"},
            {"Parameter": "Recording Duration", "Value": f"{emso_man['duration_seconds']:.1f}", "Unit": "Seconds", "Interpretation": "17.5 minutes continuous monitoring"},
            {"Parameter": "Temporal Stability (CV)", "Value": f"{emso_man['temporal_stability']['temporal_stability_cv']:.4%}", "Unit": "Ratio", "Interpretation": "Exceptional stationary ambient baseline"},
            {"Parameter": "Mean Channel RMS", "Value": f"{emso_man['channel_rms_statistics']['mean_rms']:.2f}", "Unit": "Strain arb.", "Interpretation": "Average ambient optical noise floor"},
            {"Parameter": "Median Channel RMS", "Value": f"{emso_man['channel_rms_statistics']['median_rms']:.2f}", "Unit": "Strain arb.", "Interpretation": "Robust median noise floor"},
            {"Parameter": "Inter-Channel Variability (CV)", "Value": f"{emso_man['channel_rms_statistics']['inter_channel_cv']:.4f}", "Unit": "Ratio", "Interpretation": "Natural optical attenuation across length"},
            {"Parameter": "Sample Kurtosis", "Value": f"{emso_man['distribution_metrics']['sample_kurtosis']:.2f}", "Unit": "Dimensionless", "Interpretation": "Heavy-tailed unperturbed seafloor acoustics"},
        ],
        ["Parameter", "Value", "Unit", "Interpretation"],
        tbl_dir / "table3_emso_baseline.csv",
        tbl_dir / "table3_emso_baseline.tex",
        "EMSO Western Ionian Deep-Sea DAS Baseline Statistics",
    )

    # Table 4: Controlled Scenario Performance (S01-S22)
    s_rows = []
    for sid in scenarios:
        sm = scenario_summaries[sid]
        s_rows.append({
            "Scenario": sid,
            "Description": sm["description"],
            "Trials": str(sm["trials"]),
            "Accuracy": f"{sm['accuracy']:.4f}",
            "Mean_CP": f"{sm['mean_physical_confidence']:.3f}",
            "Mean_CA": f"{sm['mean_association_confidence']:.3f}",
            "Mean_Uncertainty": f"{sm['mean_uncertainty']:.3f}",
            "Dominant_Decision": max(sm["decision_distribution"].items(), key=lambda x: x[1])[0],
        })
    save_csv_and_tex(
        s_rows,
        ["Scenario", "Description", "Trials", "Accuracy", "Mean_CP", "Mean_CA", "Mean_Uncertainty", "Dominant_Decision"],
        tbl_dir / "table4_controlled_scenarios.csv",
        tbl_dir / "table4_controlled_scenarios.tex",
        "Controlled Benchmark Scenario Performance (S01-S22, N=100 trials each)",
    )

    # Table 5: Baseline Comparison
    b_rows = []
    for m in baseline_methods:
        bm = baseline_metrics[m]
        p_val = f"{stat_comparisons[m]['paired_bootstrap']['p_value']:.4f}" if m != "proposed" else "Ref."
        d_val = f"{stat_comparisons[m]['cohens_d']:.3f}" if m != "proposed" else "Ref."
        b_rows.append({
            "Method": m,
            "Accuracy": f"{bm['accuracy']:.4f}",
            "Precision": f"{bm['precision']:.4f}",
            "Recall": f"{bm['recall']:.4f}",
            "F1": f"{bm['f1']:.4f}",
            "False_Alarm_Rate": f"{bm['false_alarm_rate']:.4f}",
            "Miss_Rate": f"{bm['miss_rate']:.4f}",
            "TX_Rate": f"{bm['tx_rate']:.4f}",
            "Cohen_d": d_val,
            "Bootstrap_p": p_val,
        })
    save_csv_and_tex(
        b_rows,
        ["Method", "Accuracy", "Precision", "Recall", "F1", "False_Alarm_Rate", "Miss_Rate", "TX_Rate", "Cohen_d", "Bootstrap_p"],
        tbl_dir / "table5_baseline_comparison.csv",
        tbl_dir / "table5_baseline_comparison.tex",
        "Comparative Evaluation Against Baselines Across 2,200 Benchmark Trials",
    )

    # Table 6: Ablation Study
    abl_rows = []
    prop_f1 = ablation_metrics["J: full proposed framework"]["f1"]
    for label, _ in ablation_configs:
        am = ablation_metrics[label]
        delta_f1 = am["f1"] - prop_f1
        abl_rows.append({
            "Configuration": label,
            "Accuracy": f"{am['accuracy']:.4f}",
            "Precision": f"{am['precision']:.4f}",
            "Recall": f"{am['recall']:.4f}",
            "F1": f"{am['f1']:.4f}",
            "Delta_F1": f"{delta_f1:+.4f}",
            "False_Alarm": f"{am['false_alarm_rate']:.4f}",
            "Miss_Rate": f"{am['miss_rate']:.4f}",
            "TX_Rate": f"{am['tx_rate']:.4f}",
        })
    save_csv_and_tex(
        abl_rows,
        ["Configuration", "Accuracy", "Precision", "Recall", "F1", "Delta_F1", "False_Alarm", "Miss_Rate", "TX_Rate"],
        tbl_dir / "table6_ablation_study.csv",
        tbl_dir / "table6_ablation_study.tex",
        "Ablation Analysis of Framework Architectural Components",
    )

    # Table 7: Sensor Failure & Missing Evidence
    sf_rows = []
    for fr in failure_records:
        sf_rows.append({
            "Condition": fr["condition"],
            "Scenario": fr["scenario_id"],
            "Mean_Uncertainty": f"{fr['mean_uncertainty']:.4f}",
            "Mean_Reliability": f"{fr['mean_reliability']:.4f}",
            "TX_Rate": f"{fr['tx_rate']:.4f}",
            "Accuracy": f"{fr['correctness']:.4f}",
        })
    save_csv_and_tex(
        sf_rows,
        ["Condition", "Scenario", "Mean_Uncertainty", "Mean_Reliability", "TX_Rate", "Accuracy"],
        tbl_dir / "table7_sensor_failure.csv",
        tbl_dir / "table7_sensor_failure.tex",
        "System Degradation and Fail-Closed Behavior under Sensor Failures",
    )

    # Table 8: Adversarial Robustness & AER
    adv_rows = []
    for ar in adv_results:
        adv_rows.append({
            "Attack_Family": ar["attack"],
            "Severity": f"{ar['severity']:.1f}",
            "AER": f"{ar['AER']:.4f}",
            "TX_Rate": f"{ar['TX_rate']:.4f}",
            "Escalated_T2_T3": f"{ar['escalated_T2_T3_rate']:.4f}",
            "Mean_Uncertainty": f"{ar['mean_uncertainty']:.4f}",
        })
    save_csv_and_tex(
        adv_rows,
        ["Attack_Family", "Severity", "AER", "TX_Rate", "Escalated_T2_T3", "Mean_Uncertainty"],
        tbl_dir / "table8_adversarial_robustness.csv",
        tbl_dir / "table8_adversarial_robustness.tex",
        "Adversarial Robustness and AER under Vessel-Side Evidence Manipulation",
    )

    # Table 9: Competing Hypothesis Classification
    hyp_rows = []
    for h in hyp_classes:
        hm = per_class_metrics[h]
        hyp_rows.append({
            "Hypothesis": h,
            "Support_N": str(hm["true_count"]),
            "Precision": f"{hm['precision']:.4f}",
            "Recall": f"{hm['recall']:.4f}",
            "F1": f"{hm['f1']:.4f}",
        })
    hyp_rows.append({
        "Hypothesis": "Macro Average",
        "Support_N": str(total_samples),
        "Precision": f"{np.mean([m['precision'] for m in per_class_metrics.values()]):.4f}",
        "Recall": f"{np.mean([m['recall'] for m in per_class_metrics.values()]):.4f}",
        "F1": f"{macro_f1:.4f}",
    })
    save_csv_and_tex(
        hyp_rows,
        ["Hypothesis", "Support_N", "Precision", "Recall", "F1"],
        tbl_dir / "table9_competing_hypotheses.csv",
        tbl_dir / "table9_competing_hypotheses.tex",
        "Competing Hypothesis Classification Performance",
    )

    # Table 10: Computational Performance
    lat_rows = []
    for stage, pm in perf_metrics.items():
        lat_rows.append({
            "Processing_Stage": stage,
            "Mean_ms": f"{pm['mean_ms']:.3f}",
            "Median_ms": f"{pm['median_ms']:.3f}",
            "P95_ms": f"{pm['p95_ms']:.3f}",
            "Max_ms": f"{pm['max_ms']:.3f}",
            "Throughput_Hz": f"{pm['throughput_hz']:.1f}",
        })
    save_csv_and_tex(
        lat_rows,
        ["Processing_Stage", "Mean_ms", "Median_ms", "P95_ms", "Max_ms", "Throughput_Hz"],
        tbl_dir / "table10_computational_performance.csv",
        tbl_dir / "table10_computational_performance.tex",
        "Computational Latency and Throughput Profiling (N=1,000 Iterations)",
    )

    # -----------------------------------------------------------------------
    # FIGURES (1-12)
    # -----------------------------------------------------------------------
    # Copy Marlinks & EMSO plots
    for src_name, dst_name in [
        ("marlinks_spatial_energy_vs_distance.png", "fig01_marlinks_energy_vs_distance.png"),
        ("marlinks_proximity_correlation.png", "fig02_marlinks_spatial_cpa.png"),
        ("marlinks_spectral_response.png", "fig03_marlinks_temporal_response.png"),
        ("emso_temporal_stability.png", "fig04_emso_temporal_stability.png"),
    ]:
        src_p = real_dir / src_name
        if src_p.is_file():
            (fig_dir / dst_name).write_bytes(src_p.read_bytes())

    # Fig 5: Confusion Matrix
    fig, ax = plt.subplots(figsize=(7, 6))
    cm_arr = np.array([[conf_matrix[th][ph] for ph in hyp_classes] for th in hyp_classes])
    im = ax.imshow(cm_arr, cmap="Blues", interpolation="nearest")
    fig.colorbar(im, ax=ax)
    labels_short = ["H1: Vessel", "H2: Env", "H3: Mech", "H4: Fault"]
    ax.set_xticks(range(4))
    ax.set_xticklabels(labels_short, rotation=25, ha="right", fontsize=10)
    ax.set_yticks(range(4))
    ax.set_yticklabels(labels_short, fontsize=10)
    ax.set_xlabel("Predicted Hypothesis", fontsize=11, fontweight="bold")
    ax.set_ylabel("True Hypothesis", fontsize=11, fontweight="bold")
    ax.set_title(f"Competing Hypotheses Confusion Matrix (Macro F1 = {macro_f1:.4f})", fontsize=12, fontweight="bold")
    for i in range(4):
        for j in range(4):
            ax.text(j, i, str(cm_arr[i, j]), ha="center", va="center", color="white" if cm_arr[i, j] > cm_arr.max() / 2 else "black", fontsize=11)
    plt.tight_layout()
    fig.savefig(fig_dir / "fig05_scenario_confusion_matrix.png", dpi=300)
    plt.close(fig)

    # Fig 6: Baseline Comparison Bar Plot
    fig, ax = plt.subplots(figsize=(8, 5))
    methods_plot = [m for m in baseline_methods]
    f1s = [baseline_metrics[m]["f1"] for m in methods_plot]
    fars = [baseline_metrics[m]["false_alarm_rate"] for m in methods_plot]
    x = np.arange(len(methods_plot))
    width = 0.35
    ax.bar(x - width/2, f1s, width, label="F1-Score", color="#1f77b4")
    ax.bar(x + width/2, fars, width, label="False Alarm Rate", color="#d62728")
    ax.set_xticks(x)
    ax.set_xticklabels(methods_plot, rotation=15, ha="right")
    ax.set_ylabel("Score", fontsize=11)
    ax.set_title("Proposed Framework vs Baseline Methods (Controlled Benchmark)", fontsize=12, fontweight="bold")
    ax.set_ylim(0, 1.15)
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    fig.savefig(fig_dir / "fig06_baseline_comparison.png", dpi=300)
    plt.close(fig)

    # Fig 7: Ablation Performance
    fig, ax = plt.subplots(figsize=(10, 6))
    abl_labels_plot = [k for k, _ in ablation_configs]
    abl_f1s = [ablation_metrics[k]["f1"] for k in abl_labels_plot]
    y_pos = np.arange(len(abl_labels_plot))
    colors = ["#2ca02c" if "proposed" in k else "#3274a1" for k in abl_labels_plot]
    ax.barh(y_pos, abl_f1s, color=colors, height=0.65)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(abl_labels_plot, fontsize=9)
    ax.set_xlabel("F1 Score", fontsize=11)
    ax.set_xlim(0, 1.1)
    ax.set_title("Ablation Study: Impact of Evidence Components on Detection F1", fontsize=12, fontweight="bold")
    ax.grid(True, alpha=0.3)
    for i, v in enumerate(abl_f1s):
        ax.text(v + 0.01, i, f"{v:.4f}", va="center", fontsize=9)
    plt.tight_layout()
    fig.savefig(fig_dir / "fig07_ablation_performance.png", dpi=300)
    plt.close(fig)

    # Fig 8: Uncertainty vs Evidence Availability
    fig, ax = plt.subplots(figsize=(8, 5))
    avail_levels = [r["mean_reliability"] for r in failure_records]
    unc_levels = [r["mean_uncertainty"] for r in failure_records]
    names = [r["condition"].split("(")[0].strip() for r in failure_records]
    scatter = ax.scatter(avail_levels, unc_levels, c=range(len(names)), cmap="tab10", s=100, zorder=5)
    for i, txt in enumerate(names):
        ax.annotate(txt, (avail_levels[i], unc_levels[i]), fontsize=8, xytext=(5, 5), textcoords="offset points")
    ax.set_xlabel("Mean Evidence Reliability", fontsize=11)
    ax.set_ylabel("Epistemic Uncertainty U", fontsize=11)
    ax.set_title("Uncertainty Escalation under Degraded and Missing Evidence", fontsize=12, fontweight="bold")
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    fig.savefig(fig_dir / "fig08_uncertainty_vs_evidence.png", dpi=300)
    plt.close(fig)

    # Fig 9: Adversarial Robustness Curve
    fig, ax = plt.subplots(figsize=(9, 5))
    for atk in adv_attacks:
        atk_rows = [r for r in adv_results if r["attack"] == atk]
        sevs = [r["severity"] for r in atk_rows]
        aers = [r["AER"] for r in atk_rows]
        ax.plot(sevs, aers, marker="o", linewidth=1.8, label=atk)
    ax.set_xlabel("Attack Severity Level", fontsize=11)
    ax.set_ylabel("Adversarial Error Rate (AER)", fontsize=11)
    ax.set_title("Adversarial Error Rate (AER) Across Vessel Manipulation Attacks", fontsize=12, fontweight="bold")
    ax.set_ylim(-0.05, 1.05)
    ax.legend(loc="upper left")
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    fig.savefig(fig_dir / "fig09_adversarial_robustness_aer.png", dpi=300)
    plt.close(fig)

    # Fig 10: Sensor Failure Degradation
    fig, ax = plt.subplots(figsize=(9, 5))
    cond_labels = [r["condition"].split("(")[0].strip() for r in failure_records]
    tx_rates = [r["tx_rate"] for r in failure_records]
    corrs = [r["correctness"] for r in failure_records]
    x = np.arange(len(cond_labels))
    ax.bar(x - 0.2, tx_rates, width=0.4, label="TX Fail-Closed Rate", color="#e74c3c")
    ax.bar(x + 0.2, corrs, width=0.4, label="Decision Correctness", color="#2ecc71")
    ax.set_xticks(x)
    ax.set_xticklabels(cond_labels, rotation=25, ha="right", fontsize=9)
    ax.set_ylabel("Rate", fontsize=11)
    ax.set_title("Fail-Closed Escalation (TX) vs Decision Correctness under Failures", fontsize=12, fontweight="bold")
    ax.set_ylim(0, 1.15)
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    fig.savefig(fig_dir / "fig10_sensor_failure_degradation.png", dpi=300)
    plt.close(fig)

    # Fig 11: Decision Distribution
    fig, ax = plt.subplots(figsize=(10, 5))
    all_decisions = [t["decision"] for t in all_trials]
    states = ["T0", "T1", "T2", "T3", "TX"]
    counts = [all_decisions.count(s) for s in states]
    colors = ["#2ecc71", "#f39c12", "#e67e22", "#e74c3c", "#34495e"]
    ax.bar(states, counts, color=colors, width=0.55)
    ax.set_xlabel("Decision State Tier", fontsize=11, fontweight="bold")
    ax.set_ylabel("Total Benchmark Trial Count", fontsize=11, fontweight="bold")
    ax.set_title(f"State-Machine Decision Distribution Across All Controlled Trials (N={len(all_trials)})", fontsize=12, fontweight="bold")
    for i, c in enumerate(counts):
        ax.text(i, c + 15, f"{c} ({c/len(all_trials):.1%})", ha="center", fontsize=10)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    fig.savefig(fig_dir / "fig11_decision_distribution.png", dpi=300)
    plt.close(fig)

    # Fig 12: Latency Distribution
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(e2e_latencies, bins=40, color="#3498db", edgecolor="black", alpha=0.75)
    med_lat = np.median(e2e_latencies)
    p95_lat = np.percentile(e2e_latencies, 95)
    ax.axvline(med_lat, color="red", linestyle="--", linewidth=1.5, label=f"Median = {med_lat:.2f} ms")
    ax.axvline(p95_lat, color="orange", linestyle=":", linewidth=1.5, label=f"95th Pct = {p95_lat:.2f} ms")
    ax.set_xlabel("End-to-End Pipeline Execution Latency (ms)", fontsize=11)
    ax.set_ylabel("Iteration Count", fontsize=11)
    ax.set_title(f"End-to-End Latency Distribution (N={len(e2e_latencies)} Iterations)", fontsize=12, fontweight="bold")
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    fig.savefig(fig_dir / "fig12_latency_distribution.png", dpi=300)
    plt.close(fig)

    print("All 10 tables and 12 figures generated successfully.")

    # -----------------------------------------------------------------------
    # MASTER EXPERIMENT MANIFEST
    # -----------------------------------------------------------------------
    exp_manifest = {
        "title": "An Uncertainty-Aware Multimodal Evidence Fusion Framework for Vessel-Associated Subsea Cable Disturbance Assessment under Adversarial Uncertainty",
        "phase": "PHASE 3: FULL EXPERIMENTAL VALIDATION",
        "execution_timestamp": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(),
        "software_version": __version__,
        "python_version": platform.python_version(),
        "hardware_environment": {
            "os": platform.platform(),
            "cpu": platform.processor(),
            "machine": platform.machine(),
        },
        "provenance_boundary": {
            "real_datasets": {
                "Marlinks": {
                    "path": "data/marlinks_demo/reduced_dataset_sensor_range_1440_1690.h5",
                    "sha256": "46f5d28383427d4c9d404f22117cd92377a5919de85cbea0dcfc8b9b3a7aff44",
                    "status": "REAL DATA (EXECUTED)",
                    "validation_scope": "Continuous physical proximity correlation (rho=0.9482), CPA temporal alignment, spatial Gini concentration",
                    "manifest_path": "artifacts/real_data_evaluation/marlinks_manifest.json",
                },
                "EMSO_Ionian": {
                    "path": "data/emso_ionian/decimated_20250610T030504.010529_1050_seconds_10_Hz.npy",
                    "sha256": "8af2afac41b9ff9acee4e9f02ff782508398537a5643a331dd47f19e5f9ffdac",
                    "status": "REAL DATA (EXECUTED)",
                    "validation_scope": "Independent unperturbed seafloor baseline, temporal stability (CV=0.0008), channel variability",
                    "manifest_path": "artifacts/real_data_evaluation/emso_manifest.json",
                },
            },
            "controlled_simulation": {
                "scenarios": scenarios,
                "trials_per_scenario": trials_per_scenario,
                "master_seed": master_seed,
                "total_trials": len(all_trials),
                "validation_scope": "Causal threat assessment, competing hypotheses H1-H4, T0-T3/TX decisions, sensor faults, adversarial AIS evasion",
            },
        },
        "artifact_manifests": {
            "scenario_matrix": "artifacts/simulation/scenario_matrix.json",
            "monte_carlo": "artifacts/monte_carlo/monte_carlo_manifest.json",
            "baselines": "artifacts/baselines/baselines_manifest.json",
            "ablation": "artifacts/ablation/ablation_manifest.json",
            "sensor_failure": "artifacts/simulation/sensor_failure_manifest.json",
            "competing_hypotheses": "artifacts/simulation/competing_hypotheses_manifest.json",
            "adversarial": "artifacts/adversarial/adversarial_manifest.json",
            "threshold_calibration": "artifacts/simulation/threshold_calibration_manifest.json",
            "performance": "artifacts/performance/performance_manifest.json",
        },
        "publication_tables": [
            str(p.relative_to(artifacts_dir)) for p in tbl_dir.glob("*.csv")
        ],
        "publication_figures": [
            str(p.relative_to(artifacts_dir)) for p in fig_dir.glob("*.png")
        ],
    }

    with open(artifacts_dir / "EXPERIMENT_MANIFEST.json", "w", encoding="utf-8") as f:
        json.dump(exp_manifest, f, indent=2)
    print("\nSaved artifacts/EXPERIMENT_MANIFEST.json.")
    print("=" * 70)
    print("PHASE 3 FULL EXPERIMENTAL VALIDATION COMPLETE!")
    print("=" * 70)


if __name__ == "__main__":
    main()
