from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from .models import VesselObservation

SUPPORTED_ATTACKS = frozenset({"none", "ais_spoofing", "transponder_suppression", "timestamp_manipulation"})


def spoof_position(vessel: VesselObservation, position: tuple[float, float]) -> VesselObservation:
    return replace(vessel, position=position, metadata={**vessel.metadata, "attack": "ais_position_spoofing"})


def suppress_transponder(vessel: VesselObservation) -> VesselObservation:
    return replace(vessel, reported=False, metadata={**vessel.metadata, "attack": "transponder_suppression"})


def manipulate_timestamp(vessel: VesselObservation, offset: float) -> VesselObservation:
    return replace(vessel, timestamp=vessel.timestamp + offset, metadata={**vessel.metadata, "attack": "timestamp_manipulation", "offset": offset})


def apply_attack(vessel: VesselObservation, attack: str, severity: float = 1.0) -> VesselObservation:
    if not 0 <= severity <= 1:
        raise ValueError("severity must be in [0, 1]")
    if attack not in SUPPORTED_ATTACKS:
        raise ValueError(f"unsupported attack: {attack}")
    if attack == "ais_spoofing":
        distance = 10.0 + 20.0 * severity
        return spoof_position(vessel, (distance, distance))
    if attack == "transponder_suppression":
        return suppress_transponder(vessel)
    if attack == "timestamp_manipulation":
        return manipulate_timestamp(vessel, 10.0 * severity)
    if attack == "none":
        return vessel
    return vessel
