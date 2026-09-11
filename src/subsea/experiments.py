from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile

from .adversarial import SUPPORTED_ATTACKS, apply_attack
from .baselines import METHODS, evaluate_method
from .metrics import adversarial_error_rate, false_high_escalation_rate, pending_result
from .pipeline import run_pipeline
from .simulation import generate_observations, make_scenario, scenario_manifest


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
    for trial in range(trials):
        scenario = make_scenario(scenario_id, seed + trial)
        observations, vessel = generate_observations(scenario)
        if vessel is not None:
            vessel = apply_attack(vessel, attack, attack_severity)
        result = run_pipeline(observations, vessel, environmental_event=scenario.environmental_event)
        predictions.append({
            "trial": trial,
            "seed": seed + trial,
            "decision": result.decision.value,
            "confidence": result.reliability,
            "uncertainty": result.uncertainty,
            "attack": attack,
            "attack_severity": attack_severity,
            "true_h1": scenario.vessel_present and scenario.disturbance_present and not scenario.environmental_event,
            "attack_applied": attack != "none" and scenario.vessel_present and scenario.disturbance_present and not scenario.environmental_event,
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
        "predictions": predictions,
    }
    manifest_path = output / "experiment_manifest.json"
    with NamedTemporaryFile("w", encoding="utf-8", dir=output, prefix=".manifest-", delete=False) as temporary:
        temporary.write(json.dumps(manifest, indent=2) + "\n")
        temporary_path = Path(temporary.name)
    temporary_path.replace(manifest_path)
    return manifest_path


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
            result = run_pipeline(observations, vessel, environmental_event=scenario.environmental_event)
            records.extend(evaluate_method(method, result, scenario) for method in methods)
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
