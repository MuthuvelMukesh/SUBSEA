from __future__ import annotations

from collections.abc import Iterable

import numpy as np

from .models import Evidence, Hypothesis


def weighted_fusion(evidence: Iterable[Evidence], epsilon: float = 1e-12) -> tuple[float, float]:
    values = tuple(evidence)
    if not values:
        return 0.0, 1.0
    numerator = sum(item.weight * item.health * item.availability * item.value for item in values)
    denominator = sum(item.weight * item.health * item.availability for item in values) + epsilon
    reliability = float(np.clip(denominator / (sum(item.weight for item in values) + epsilon), 0, 1))
    return float(np.clip(numerator / denominator, 0, 1)), reliability


def score_hypotheses(
    physical_confidence: float,
    association_confidence: float,
    reliability: float,
    *,
    environmental: float = 0.0,
    mechanical: float = 0.0,
    sensor_fault: float = 0.0,
    counter_evidence: float = 0.0,
) -> dict[str, float]:
    vessel = np.clip((0.45 * physical_confidence + 0.55 * association_confidence) * reliability - counter_evidence, 0, 1)
    scores = {
        Hypothesis.VESSEL_DISTURBANCE.value: float(vessel),
        Hypothesis.ENVIRONMENTAL.value: float(np.clip(environmental, 0, 1)),
        Hypothesis.MECHANICAL.value: float(np.clip(mechanical, 0, 1)),
        Hypothesis.SENSOR_FAULT.value: float(np.clip(sensor_fault + (1 - reliability), 0, 1)),
    }
    total = sum(scores.values())
    return {key: float(value / total) for key, value in scores.items()} if total else {key: 0.0 for key in scores}
