from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile

from .adversarial import SUPPORTED_ATTACKS, apply_attack
from .baselines import METHODS, evaluate_method
from .metrics import adversarial_error_rate, false_high_escalation_rate, pending_result
from .pipeline import run_pipeline
from .simulation import generate_observations, generate_vessels, make_scenario, scenario_manifest


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
        "status": "EXECUTED",
        "data_kind": "synthetic",
        "causal_ground_truth": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "scenario": scenario_manifest(make_scenario(scenario_id, seed)),
        "trials": trials,
        "seed": seed,
        "attack": attack,
        "attack_severity": attack_severity,
        "metrics": {"AER": aer, "FHER": fher},
        "latencies": latencies,
        "predictions": predictions,
    }
    manifest_path = output / "experiment_manifest.json"
    with NamedTemporaryFile("w", encoding="utf-8", dir=output, prefix=".manifest-", delete=False) as temporary:
        temporary.write(json.dumps(manifest, indent=2) + "\n")
        temporary_path = Path(temporary.name)
    temporary_path.replace(manifest_path)
    return manifest_path


def run_attack_severity_sweep(scenario_id: str, trials: int, seed: int, output: Path, *, attack: str = "ais_spoofing", severities: tuple[float, ...] = tuple(index / 10 for index in range(11))) -> Path:
    if not severities or any(not 0 <= severity <= 1 for severity in severities):
        raise ValueError("severities must be non-empty values in [0, 1]")
    output.mkdir(parents=True, exist_ok=False)
    rows: list[dict[str, object]] = []
    for severity in severities:
        trial_output = output / f"severity-{severity:.12g}"
        manifest_path = run_trials(scenario_id, trials, seed, trial_output, attack=attack, attack_severity=severity)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        rows.append({"attack": attack, "severity": severity, "AER": manifest["metrics"]["AER"], "FHER": manifest["metrics"]["FHER"], "trials": trials, "seed": seed})
    sweep = {"status": "EXECUTED", "data_kind": "synthetic", "scenario_id": scenario_id, "attack": attack, "trials": trials, "seed": seed, "rows": rows}
    path = output / "severity_sweep.json"
    with NamedTemporaryFile("w", encoding="utf-8", dir=output, prefix=".sweep-", delete=False) as temporary:
        temporary.write(json.dumps(sweep, indent=2) + "\n")
        temporary_path = Path(temporary.name)
    temporary_path.replace(path)
    return path


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
        "status": "EXECUTED",
        "data_kind": "synthetic",
        "causal_ground_truth": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "scenario_ids": scenario_ids,
        "trials": trials,
        "seed": seed,
        "methods": list(methods),
        "summaries": summaries,
        "records": records,
    }
    manifest_path = output / "method_comparison.json"
    with NamedTemporaryFile("w", encoding="utf-8", dir=output, prefix=".comparison-", delete=False) as temporary:
        temporary.write(json.dumps(manifest, indent=2) + "\n")
        temporary_path = Path(temporary.name)
    temporary_path.replace(manifest_path)
    return manifest_path


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
