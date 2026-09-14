from __future__ import annotations

import json
import time
import subprocess
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import numpy as np

from . import __version__
from .adversarial import SUPPORTED_ATTACKS, apply_attack
from .baselines import METHODS, evaluate_method
from .decision import decide
from .metrics import (
    adversarial_error_rate, brier_score, bootstrap_confidence_interval,
    calibration_curve, classification_metrics, expected_calibration_error,
    false_high_escalation_rate, pending_result,
)
from .pipeline import run_pipeline, run_multi_vessel_pipeline
from .simulation import (
    SUPPORTED_SCENARIOS, generate_multi_node_observations,
    generate_observations, generate_vessels, make_scenario, scenario_manifest,
)


# ---------------------------------------------------------------------------
# Provenance helpers
# ---------------------------------------------------------------------------

def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL, text=True,
        ).strip()
    except Exception:
        return "unknown"


def _base_manifest(*, data_kind: str = "synthetic") -> dict[str, Any]:
    return {
        "status": "EXECUTED",
        "data_kind": data_kind,
        "causal_ground_truth": False,
        "software_version": __version__,
        "git_commit": _git_commit(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _write_manifest(data: dict[str, Any], path: Path) -> Path:
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=parent, prefix=".manifest-", delete=False) as tmp:
        tmp.write(json.dumps(data, indent=2, default=str) + "\n")
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)
    return path


# ---------------------------------------------------------------------------
# Core trial runner (backward compatible)
# ---------------------------------------------------------------------------

def run_trials(
    scenario_id: str,
    trials: int,
    seed: int,
    output: Path,
    *,
    attack: str = "none",
    attack_severity: float = 1.0,
) -> Path:
    if trials <= 0:
        raise ValueError("trials must be positive")
    if attack not in SUPPORTED_ATTACKS:
        raise ValueError(f"unsupported attack: {attack}")
    if not 0 <= attack_severity <= 1:
        raise ValueError("attack_severity must be in [0, 1]")
    output.mkdir(parents=True, exist_ok=False)
    predictions = []
    latencies = []
    for trial in range(trials):
        scenario = make_scenario(scenario_id, seed + trial)
        observations, vessel = generate_observations(scenario)
        started = time.perf_counter()
        candidates = list(generate_vessels(scenario, tuple(item.timestamp for item in observations)))
        attacked_candidates = [apply_attack(candidate, attack, attack_severity) for candidate in candidates]
        results = [run_pipeline(observations, candidate, environmental_event=scenario.environmental_event) for candidate in attacked_candidates]
        result = max(results, key=lambda item: item.association_confidence) if results else run_pipeline(observations, None, environmental_event=scenario.environmental_event)
        latency_ms = (time.perf_counter() - started) * 1000.0
        latencies.append({"trial": trial, "seed": seed + trial, "latency_ms": latency_ms})
        predictions.append({
            "trial": trial,
            "seed": seed + trial,
            "decision": result.decision.value,
            "confidence": result.reliability,
            "uncertainty": result.uncertainty,
            "physical_confidence": result.physical_confidence,
            "association_confidence": result.association_confidence,
            "reliability": result.reliability,
            "hypothesis_scores": result.hypothesis_scores,
            "attack": attack,
            "attack_severity": attack_severity,
            "true_h1": scenario.vessel_present and scenario.disturbance_present and not scenario.environmental_event,
            "attack_requested": attack != "none" and vessel is not None,
            "attack_applied": attack != "none" and attack_severity > 0 and bool(attacked_candidates),
            "vessel_count": len(attacked_candidates),
            "vessel_ids": [candidate.vessel_id for candidate in attacked_candidates],
            "benign": not scenario.vessel_present and not scenario.environmental_event,
        })
    decisions = [item["decision"] for item in predictions]
    adversarial_h1 = [item["true_h1"] and item["attack_applied"] for item in predictions]
    benign = [item["benign"] for item in predictions]
    try:
        aer: dict[str, object] = {"status": "EXECUTED", "value": adversarial_error_rate(decisions, adversarial_h1), "reason": None}
    except ValueError as error:
        aer = pending_result(str(error))
    try:
        fher: dict[str, object] = {"status": "EXECUTED", "value": false_high_escalation_rate(decisions, benign), "reason": None}
    except ValueError as error:
        fher = pending_result(str(error))
    manifest = {
        **_base_manifest(),
        "scenario": scenario_manifest(make_scenario(scenario_id, seed)),
        "trials": trials,
        "seed": seed,
        "attack": attack,
        "attack_severity": attack_severity,
        "metrics": {"AER": aer, "FHER": fher},
        "latencies": latencies,
        "predictions": predictions,
    }
    return _write_manifest(manifest, output / "experiment_manifest.json")


# ---------------------------------------------------------------------------
# Attack severity sweep
# ---------------------------------------------------------------------------

def run_attack_severity_sweep(
    scenario_id: str, trials: int, seed: int, output: Path,
    *, attack: str = "ais_spoofing",
    severities: tuple[float, ...] = tuple(index / 10 for index in range(11)),
) -> Path:
    if not severities or any(not 0 <= severity <= 1 for severity in severities):
        raise ValueError("severities must be non-empty values in [0, 1]")
    output.mkdir(parents=True, exist_ok=False)
    rows: list[dict[str, object]] = []
    for severity in severities:
        trial_output = output / f"severity-{severity:.12g}"
        manifest_path = run_trials(scenario_id, trials, seed, trial_output, attack=attack, attack_severity=severity)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        # Decision distribution
        preds = manifest.get("predictions", [])
        decision_dist = {}
        for p in preds:
            d = p["decision"]
            decision_dist[d] = decision_dist.get(d, 0) + 1
        uncertainties = [p["uncertainty"] for p in preds]
        rows.append({
            "attack": attack, "severity": severity,
            "AER": manifest["metrics"]["AER"],
            "FHER": manifest["metrics"]["FHER"],
            "decision_distribution": decision_dist,
            "mean_uncertainty": float(np.mean(uncertainties)) if uncertainties else None,
            "trials": trials, "seed": seed,
        })
    sweep = {**_base_manifest(), "scenario_id": scenario_id, "attack": attack, "trials": trials, "seed": seed, "rows": rows}
    return _write_manifest(sweep, output / "severity_sweep.json")


# ---------------------------------------------------------------------------
# Method comparison (backward compatible)
# ---------------------------------------------------------------------------

def run_method_comparison(
    scenario_ids: list[str],
    trials: int,
    seed: int,
    output: Path,
    *,
    methods: tuple[str, ...] = tuple(sorted(METHODS)),
) -> Path:
    if not scenario_ids or trials <= 0:
        raise ValueError("scenario_ids must be non-empty and trials must be positive")
    if any(method not in METHODS for method in methods) or not methods:
        raise ValueError("methods must be a non-empty subset of supported methods")
    output.mkdir(parents=True, exist_ok=False)
    records: list[dict[str, object]] = []
    for scenario_index, scenario_id in enumerate(scenario_ids):
        for trial in range(trials):
            trial_seed = seed + scenario_index * trials + trial
            scenario = make_scenario(scenario_id, trial_seed)
            observations, vessel = generate_observations(scenario)
            candidates = generate_vessels(scenario, tuple(item.timestamp for item in observations))
            results = [run_pipeline(observations, candidate, environmental_event=scenario.environmental_event) for candidate in candidates]
            result = max(results, key=lambda item: item.association_confidence) if results else run_pipeline(observations, vessel, environmental_event=scenario.environmental_event)
            vessel_details = [{"vessel_id": candidate.vessel_id, "decision": candidate_result.decision.value, "association_confidence": candidate_result.association_confidence, "uncertainty": candidate_result.uncertainty} for candidate, candidate_result in zip(candidates, results)]
            for method in methods:
                record = evaluate_method(method, result, scenario)
                record["vessel_results"] = []
                for candidate, candidate_result in zip(candidates, results):
                    method_result = evaluate_method(method, candidate_result, scenario)
                    effective = method_result["inputs"]["effective_decision_inputs"]
                    record["vessel_results"].append({"vessel_id": candidate.vessel_id, "decision": method_result["decision"], "association_confidence": effective["association_confidence"], "uncertainty": effective["uncertainty"]})
                records.append(record)
    summaries = {method: _method_summary([record for record in records if record["method"] == method]) for method in methods}
    manifest = {
        **_base_manifest(),
        "scenario_ids": scenario_ids,
        "trials": trials,
        "seed": seed,
        "methods": list(methods),
        "summaries": summaries,
        "records": records,
    }
    return _write_manifest(manifest, output / "method_comparison.json")


def _method_summary(records: list[dict[str, object]]) -> dict[str, object]:
    if not records:
        return {"status": "NOT EXECUTED", "value": None, "reason": "method has no records"}
    actual = [bool(record["truth"]["vessel_present"] and record["truth"]["disturbance_present"] and not record["truth"]["environmental_event"]) for record in records]
    predicted = [record["decision"] in {"T2", "T3"} for record in records]
    true_positive = sum(left and right for left, right in zip(actual, predicted))
    false_positive = sum(not left and right for left, right in zip(actual, predicted))
    false_negative = sum(left and not right for left, right in zip(actual, predicted))
    accuracy = sum(left == right for left, right in zip(actual, predicted)) / len(actual)
    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"status": "EXECUTED", "value": {"accuracy": accuracy, "precision": precision, "recall": recall, "f1": f1, "trials": len(records)}, "reason": None}


# ---------------------------------------------------------------------------
# Noise sweep
# ---------------------------------------------------------------------------

def run_noise_sweep(
    scenario_id: str, trials: int, seed: int, output: Path,
    *, noise_levels: tuple[float, ...] = (0.0, 0.05, 0.10, 0.20, 0.30, 0.50),
) -> Path:
    if not noise_levels:
        raise ValueError("noise_levels must be non-empty")
    output.mkdir(parents=True, exist_ok=False)
    rows: list[dict[str, Any]] = []
    for noise in noise_levels:
        trial_preds: list[dict[str, Any]] = []
        for trial in range(trials):
            scenario = make_scenario(scenario_id, seed + trial)
            observations, vessel = generate_observations(scenario, noise_override=noise)
            result = run_pipeline(observations, vessel, environmental_event=scenario.environmental_event)
            is_h1 = scenario.vessel_present and scenario.disturbance_present and not scenario.environmental_event
            trial_preds.append({
                "trial": trial, "seed": seed + trial,
                "decision": result.decision.value,
                "true_h1": is_h1,
                "predicted_positive": result.decision.value in {"T2", "T3"},
                "uncertainty": result.uncertainty,
                "physical_confidence": result.physical_confidence,
                "reliability": result.reliability,
            })
        decisions = [p["decision"] for p in trial_preds]
        actual = [p["true_h1"] for p in trial_preds]
        predicted_pos = [p["predicted_positive"] for p in trial_preds]
        tp = sum(a and p for a, p in zip(actual, predicted_pos))
        fp = sum(not a and p for a, p in zip(actual, predicted_pos))
        fn = sum(a and not p for a, p in zip(actual, predicted_pos))
        acc = sum(a == p for a, p in zip(actual, predicted_pos)) / len(actual)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        benign = [not a for a in actual]
        try:
            fher_val: Any = false_high_escalation_rate(decisions, benign)
        except ValueError:
            fher_val = None
        tx_count = sum(d == "TX" for d in decisions)
        rows.append({
            "noise_level": noise,
            "accuracy": acc, "precision": prec, "recall": rec, "f1": f1,
            "FHER": fher_val,
            "TX_rate": tx_count / len(decisions),
            "mean_uncertainty": float(np.mean([p["uncertainty"] for p in trial_preds])),
            "trials": trials,
        })
    sweep = {**_base_manifest(), "scenario_id": scenario_id, "sweep_type": "noise", "trials": trials, "seed": seed, "rows": rows}
    return _write_manifest(sweep, output / "noise_sweep.json")


# ---------------------------------------------------------------------------
# Packet-loss sweep
# ---------------------------------------------------------------------------

def run_packet_loss_sweep(
    scenario_id: str, trials: int, seed: int, output: Path,
    *, loss_rates: tuple[float, ...] = (0.0, 0.05, 0.10, 0.20, 0.30, 0.50, 0.70),
) -> Path:
    if not loss_rates:
        raise ValueError("loss_rates must be non-empty")
    output.mkdir(parents=True, exist_ok=False)
    rows: list[dict[str, Any]] = []
    for loss in loss_rates:
        trial_preds: list[dict[str, Any]] = []
        for trial in range(trials):
            scenario = make_scenario(scenario_id, seed + trial)
            observations, vessel = generate_observations(scenario, packet_loss_override=loss)
            result = run_pipeline(observations, vessel, environmental_event=scenario.environmental_event)
            is_h1 = scenario.vessel_present and scenario.disturbance_present and not scenario.environmental_event
            trial_preds.append({
                "trial": trial, "seed": seed + trial,
                "decision": result.decision.value,
                "true_h1": is_h1,
                "predicted_positive": result.decision.value in {"T2", "T3"},
                "uncertainty": result.uncertainty,
                "reliability": result.reliability,
            })
        decisions = [p["decision"] for p in trial_preds]
        actual = [p["true_h1"] for p in trial_preds]
        predicted_pos = [p["predicted_positive"] for p in trial_preds]
        tp = sum(a and p for a, p in zip(actual, predicted_pos))
        fp = sum(not a and p for a, p in zip(actual, predicted_pos))
        fn = sum(a and not p for a, p in zip(actual, predicted_pos))
        f1_val = 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0
        benign = [not a for a in actual]
        try:
            fher_val: Any = false_high_escalation_rate(decisions, benign)
        except ValueError:
            fher_val = None
        tx_count = sum(d == "TX" for d in decisions)
        rows.append({
            "packet_loss_rate": loss,
            "f1": f1_val,
            "FHER": fher_val,
            "TX_rate": tx_count / len(decisions),
            "mean_uncertainty": float(np.mean([p["uncertainty"] for p in trial_preds])),
            "mean_reliability": float(np.mean([p["reliability"] for p in trial_preds])),
            "trials": trials,
        })
    sweep = {**_base_manifest(), "scenario_id": scenario_id, "sweep_type": "packet_loss", "trials": trials, "seed": seed, "rows": rows}
    return _write_manifest(sweep, output / "packet_loss_sweep.json")


# ---------------------------------------------------------------------------
# Position-uncertainty sweep
# ---------------------------------------------------------------------------

def run_position_uncertainty_sweep(
    scenario_id: str, trials: int, seed: int, output: Path,
    *, uncertainty_levels: tuple[float, ...] = (0.0, 1.0, 2.0, 5.0, 10.0, 20.0),
) -> Path:
    if not uncertainty_levels:
        raise ValueError("uncertainty_levels must be non-empty")
    output.mkdir(parents=True, exist_ok=False)
    rows: list[dict[str, Any]] = []
    for unc in uncertainty_levels:
        trial_preds: list[dict[str, Any]] = []
        for trial in range(trials):
            from dataclasses import replace as dc_replace
            scenario = make_scenario(scenario_id, seed + trial)
            scenario = dc_replace(scenario, position_uncertainty_level=unc)
            observations, _ = generate_observations(scenario)
            vessels = generate_vessels(scenario, tuple(o.timestamp for o in observations))
            vessel = vessels[0] if vessels else None
            result = run_pipeline(observations, vessel, environmental_event=scenario.environmental_event)
            trial_preds.append({
                "trial": trial, "seed": seed + trial,
                "decision": result.decision.value,
                "association_confidence": result.association_confidence,
                "uncertainty": result.uncertainty,
            })
        decisions = [p["decision"] for p in trial_preds]
        tx_count = sum(d == "TX" for d in decisions)
        rows.append({
            "position_uncertainty": unc,
            "mean_association_confidence": float(np.mean([p["association_confidence"] for p in trial_preds])),
            "mean_uncertainty": float(np.mean([p["uncertainty"] for p in trial_preds])),
            "TX_rate": tx_count / len(decisions),
            "decision_distribution": {d: sum(1 for x in decisions if x == d) for d in set(decisions)},
            "trials": trials,
        })
    sweep = {**_base_manifest(), "scenario_id": scenario_id, "sweep_type": "position_uncertainty", "trials": trials, "seed": seed, "rows": rows}
    return _write_manifest(sweep, output / "position_uncertainty_sweep.json")


# ---------------------------------------------------------------------------
# Monte Carlo
# ---------------------------------------------------------------------------

def run_monte_carlo(
    scenario_ids: list[str],
    trials: int,
    seed: int,
    output: Path,
    *,
    methods: tuple[str, ...] = ("proposed",),
    attack: str = "none",
    attack_severity: float = 0.0,
) -> Path:
    if trials <= 0:
        raise ValueError("trials must be positive")
    output.mkdir(parents=True, exist_ok=False)
    records: list[dict[str, Any]] = []
    for scenario_index, scenario_id in enumerate(scenario_ids):
        for trial in range(trials):
            trial_seed = seed + scenario_index * trials + trial
            scenario = make_scenario(scenario_id, trial_seed)
            observations, vessel = generate_observations(scenario)
            candidates = generate_vessels(scenario, tuple(o.timestamp for o in observations))
            attacked = [apply_attack(c, attack, attack_severity) for c in candidates] if attack != "none" else list(candidates)
            results = [run_pipeline(observations, c, environmental_event=scenario.environmental_event) for c in attacked]
            result = max(results, key=lambda r: r.association_confidence) if results else run_pipeline(observations, None, environmental_event=scenario.environmental_event)
            is_h1 = scenario.vessel_present and scenario.disturbance_present and not scenario.environmental_event
            for method in methods:
                method_result = evaluate_method(method, result, scenario)
                records.append({
                    "master_seed": seed,
                    "trial_seed": trial_seed,
                    "trial": trial,
                    "scenario_id": scenario_id,
                    "method": method,
                    "attack": attack,
                    "attack_severity": attack_severity,
                    "true_h1": is_h1,
                    "decision": method_result["decision"],
                    "confidence": result.reliability,
                    "uncertainty": result.uncertainty,
                    "physical_confidence": result.physical_confidence,
                    "association_confidence": result.association_confidence,
                })
    manifest = {
        **_base_manifest(),
        "experiment_type": "monte_carlo",
        "scenario_ids": scenario_ids,
        "trials": trials,
        "seed": seed,
        "methods": list(methods),
        "attack": attack,
        "attack_severity": attack_severity,
        "total_records": len(records),
        "records": records,
    }
    return _write_manifest(manifest, output / "monte_carlo.json")


# ---------------------------------------------------------------------------
# All-scenario evaluation
# ---------------------------------------------------------------------------

def run_all_scenarios(
    trials: int,
    seed: int,
    output: Path,
) -> Path:
    scenario_ids = sorted(SUPPORTED_SCENARIOS)
    return run_method_comparison(scenario_ids, trials, seed, output, methods=("proposed",))


# ---------------------------------------------------------------------------
# Ablation study
# ---------------------------------------------------------------------------

ABLATION_VARIANTS = (
    "proposed",
    "without_uncertainty",
    "without_health",
    "without_counter_evidence",
    "without_spatial_temporal_association",
    "without_behaviour",
)


def run_ablation_study(
    scenario_ids: list[str],
    trials: int,
    seed: int,
    output: Path,
) -> Path:
    return run_method_comparison(
        scenario_ids, trials, seed, output,
        methods=ABLATION_VARIANTS,
    )


# ---------------------------------------------------------------------------
# Calibration analysis
# ---------------------------------------------------------------------------

def run_calibration_analysis(
    scenario_ids: list[str],
    trials: int,
    seed: int,
    output: Path,
) -> Path:
    output.mkdir(parents=True, exist_ok=False)
    labels: list[int] = []
    probabilities: list[float] = []
    for scenario_index, scenario_id in enumerate(scenario_ids):
        for trial in range(trials):
            trial_seed = seed + scenario_index * trials + trial
            scenario = make_scenario(scenario_id, trial_seed)
            observations, vessel = generate_observations(scenario)
            result = run_pipeline(observations, vessel, environmental_event=scenario.environmental_event)
            is_h1 = scenario.vessel_present and scenario.disturbance_present and not scenario.environmental_event
            labels.append(1 if is_h1 else 0)
            # Use reliability as the calibrated confidence score
            probabilities.append(float(np.clip(result.reliability, 0, 1)))

    try:
        bs = brier_score(labels, probabilities)
    except ValueError:
        bs = None
    try:
        ece = expected_calibration_error(labels, probabilities)
    except ValueError:
        ece = None
    try:
        curve = calibration_curve(labels, probabilities)
    except ValueError:
        curve = None
    try:
        ci = bootstrap_confidence_interval(probabilities)
    except ValueError:
        ci = None

    manifest = {
        **_base_manifest(),
        "experiment_type": "calibration",
        "scenario_ids": scenario_ids,
        "trials": trials,
        "seed": seed,
        "total_samples": len(labels),
        "brier_score": bs,
        "ECE": ece,
        "calibration_curve": curve,
        "confidence_interval": ci,
    }
    return _write_manifest(manifest, output / "calibration.json")


# ---------------------------------------------------------------------------
# Statistical comparison
# ---------------------------------------------------------------------------

def run_statistical_comparison(
    scenario_ids: list[str],
    trials: int,
    seed: int,
    output: Path,
    *,
    methods: tuple[str, ...] = ("proposed", "physical_only", "vessel_only", "weighted"),
) -> Path:
    from .statistics import paired_bootstrap, permutation_test, cohens_d, mcnemar_test

    output.mkdir(parents=True, exist_ok=False)
    # Collect per-trial correctness for each method
    method_correct: dict[str, list[bool]] = {m: [] for m in methods}
    method_f1_contrib: dict[str, list[float]] = {m: [] for m in methods}

    for scenario_index, scenario_id in enumerate(scenario_ids):
        for trial in range(trials):
            trial_seed = seed + scenario_index * trials + trial
            scenario = make_scenario(scenario_id, trial_seed)
            observations, vessel = generate_observations(scenario)
            candidates = generate_vessels(scenario, tuple(o.timestamp for o in observations))
            results = [run_pipeline(observations, c, environmental_event=scenario.environmental_event) for c in candidates]
            result = max(results, key=lambda r: r.association_confidence) if results else run_pipeline(observations, vessel, environmental_event=scenario.environmental_event)
            is_h1 = scenario.vessel_present and scenario.disturbance_present and not scenario.environmental_event
            for method in methods:
                m_result = evaluate_method(method, result, scenario)
                predicted_positive = m_result["decision"] in {"T2", "T3"}
                correct = (predicted_positive == is_h1)
                method_correct[method].append(correct)
                method_f1_contrib[method].append(1.0 if correct else 0.0)

    comparisons: list[dict[str, Any]] = []
    proposed_correct = method_correct.get("proposed", [])
    proposed_scores = method_f1_contrib.get("proposed", [])
    for method in methods:
        if method == "proposed":
            continue
        m_correct = method_correct[method]
        m_scores = method_f1_contrib[method]
        try:
            boot = paired_bootstrap(proposed_scores, m_scores)
        except ValueError as e:
            boot = {"status": "NOT EXECUTED", "reason": str(e)}
        try:
            perm = permutation_test(proposed_scores, m_scores)
        except ValueError as e:
            perm = {"status": "NOT EXECUTED", "reason": str(e)}
        try:
            d = cohens_d(proposed_scores, m_scores)
        except ValueError:
            d = None
        try:
            mcn = mcnemar_test(proposed_correct, m_correct)
        except (ValueError, ImportError) as e:
            mcn = {"status": "NOT EXECUTED", "reason": str(e)}
        comparisons.append({
            "method_a": "proposed",
            "method_b": method,
            "paired_bootstrap": boot,
            "permutation_test": perm,
            "cohens_d": d,
            "mcnemar": mcn,
        })

    manifest = {
        **_base_manifest(),
        "experiment_type": "statistical_comparison",
        "scenario_ids": scenario_ids,
        "trials": trials,
        "seed": seed,
        "methods": list(methods),
        "comparisons": comparisons,
    }
    return _write_manifest(manifest, output / "statistical_comparison.json")
