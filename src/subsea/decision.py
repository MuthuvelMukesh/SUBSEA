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
    # 1. Genuinely degraded sensor hardware / communication failure -> fail-closed alert
    if reliability <= limits["tx_reliability"]:
        return DecisionState.TX
    # 2. Quiet healthy window: no physical disturbance on a healthy sensor -> T0
    if physical_confidence < limits["physical"]:
        return DecisionState.T0
    # 3. Disturbance present, but evidence is conflicting / highly uncertain -> TX
    if uncertainty >= limits["tx_uncertainty"]:
        return DecisionState.TX
    # 4. Disturbance present, but uncorroborated by vessel association -> T1
    if association_confidence < limits["association"]:
        return DecisionState.T1
    # 5. Strong physical and vessel corroboration -> T2 or T3
    score = 0.5 * physical_confidence + 0.5 * association_confidence
    return DecisionState.T3 if score >= limits["t3"] and uncertainty < 0.35 else DecisionState.T2
