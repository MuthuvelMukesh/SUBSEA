from __future__ import annotations

from .models import DecisionState


def decide(
    *,
    physical_confidence: float,
    association_confidence: float,
    reliability: float,
    uncertainty: float,
    thresholds: dict[str, float] | None = None,
) -> DecisionState:
    limits = {
        "physical": 0.55,
        "association": 0.60,
        "t2": 0.65,
        "t3": 0.85,
        "tx_uncertainty": 0.65,
        "tx_reliability": 0.35,
        **(thresholds or {}),
    }
    if uncertainty >= limits["tx_uncertainty"] or reliability <= limits["tx_reliability"]:
        return DecisionState.TX
    if physical_confidence < limits["physical"]:
        return DecisionState.T0
    if association_confidence < limits["association"]:
        return DecisionState.T1
    score = 0.5 * physical_confidence + 0.5 * association_confidence
    return DecisionState.T3 if score >= limits["t3"] and uncertainty < 0.35 else DecisionState.T2
