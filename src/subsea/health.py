from __future__ import annotations

from collections.abc import Iterable

import numpy as np

from .models import SensorHealth, SensorObservation


def estimate_health(
    observations: Iterable[SensorObservation],
    *,
    expected_interval: float,
    packet_timeout: float,
    now: float | None = None,
) -> SensorHealth:
    values = tuple(observations)
    if not values or expected_interval <= 0 or packet_timeout <= 0:
        raise ValueError("observations and positive timing parameters are required")
    last = values[-1]
    timestamps = np.asarray([item.timestamp for item in values], dtype=float)
    accelerations = np.asarray([item.acceleration for item in values], dtype=float)
    missing = sum(not item.packet_received for item in values)
    stale = now is not None and now - last.timestamp > packet_timeout
    constant = bool(np.all(np.std(accelerations, axis=0) < 1e-9))
    intervals = np.diff(timestamps)
    irregular = bool(intervals.size and np.max(np.abs(intervals - expected_interval)) > expected_interval)
    communication_ok = missing == 0 and not stale
    availability = max(0.0, 1.0 - missing / len(values))
    health = availability
    reasons: list[str] = []
    if stale:
        health = 0.0
        reasons.append("stale timestamp")
    if constant:
        health *= 0.7
        reasons.append("constant-value behaviour")
    if irregular:
        health *= 0.8
        reasons.append("irregular sampling interval")
    if not communication_ok:
        reasons.append("communication degradation")
    return SensorHealth(last.node_id, float(np.clip(health, 0, 1)), availability, bool(stale), constant, communication_ok, tuple(reasons))
