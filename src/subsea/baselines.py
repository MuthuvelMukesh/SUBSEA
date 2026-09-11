from __future__ import annotations

from typing import Any

from .decision import decide
from .models import DecisionResult, Scenario

METHODS = frozenset({
    "physical_only",
    "vessel_only",
    "weighted",
    "proposed",
    "without_uncertainty",
    "without_health",
    "without_counter_evidence",
    "without_spatial_temporal_association",
    "without_behaviour",
})


def _truth(scenario: Scenario) -> dict[str, bool]:
    return {
        "vessel_present": scenario.vessel_present,
        "disturbance_present": scenario.disturbance_present,
        "environmental_event": scenario.environmental_event,
        "sensor_failure": scenario.sensor_failure,
        "spoofing": scenario.spoofing,
        "timestamp_manipulation": scenario.timestamp_manipulation,
    }


def _inputs(result: DecisionResult) -> dict[str, Any]:
    return {
        "physical_confidence": result.physical_confidence,
        "association_confidence": result.association_confidence,
        "reliability": result.reliability,
        "uncertainty": result.uncertainty,
        "hypothesis_scores": dict(result.hypothesis_scores),
    }


def _uncertainty(result: DecisionResult, *, excluded: set[str] | None = None) -> float:
    components = result.audit.get("uncertainty_components", {})
    kept = [value for name, value in components.items() if name not in (excluded or set())]
    return min(1.0, 0.25 * sum(kept))


def _association_without(result: DecisionResult, excluded: set[str]) -> float:
    components = result.audit.get("association_components", {})
    kept = [components[name] for name in ("spatial", "temporal", "behaviour") if name not in excluded]
    return sum(kept) / len(kept) if kept else 0.0


def evaluate_method(method: str, result: DecisionResult, scenario: Scenario) -> dict[str, Any]:
    if method not in METHODS:
        raise ValueError(f"unsupported evaluation method: {method}")
    effective = {
        "physical_confidence": result.physical_confidence,
        "association_confidence": result.association_confidence,
        "reliability": result.reliability,
        "uncertainty": result.uncertainty,
    }
    decision = result.decision
    changed: tuple[str, ...] = ()
    if method == "physical_only":
        effective.update(association_confidence=0.0, reliability=1.0, uncertainty=0.0)
        changed = ("association", "health", "uncertainty")
    elif method == "vessel_only":
        effective["physical_confidence"] = 0.0
        changed = ("physical",)
    elif method == "weighted":
        pass
    elif method == "without_uncertainty":
        effective["uncertainty"] = 0.0
        changed = ("uncertainty",)
    elif method == "without_health":
        effective.update(reliability=1.0, uncertainty=_uncertainty(result, excluded={"health"}))
        changed = ("health",)
    elif method == "without_counter_evidence":
        effective["uncertainty"] = float(result.audit.get("uncertainty_without_counter_evidence", result.uncertainty))
        changed = ("counter_evidence",)
    elif method == "without_spatial_temporal_association":
        effective["association_confidence"] = float(result.audit.get("association_components", {}).get("behaviour", 0.0))
        changed = ("spatial_temporal_association",)
    elif method == "without_behaviour":
        effective["association_confidence"] = _association_without(result, {"behaviour"})
        changed = ("behaviour",)
    if method != "proposed":
        decision = decide(**effective)
    return {
        "method": method,
        "method_version": "0.1",
        "scenario_id": scenario.scenario_id,
        "seed": scenario.seed,
        "decision": decision.value,
        "source_decision": result.decision.value,
        "truth": _truth(scenario),
        "inputs": {**_inputs(result), "effective_decision_inputs": effective},
        "changed_components": changed,
        "status": "EXECUTED",
    }