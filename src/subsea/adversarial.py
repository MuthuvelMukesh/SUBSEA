from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from .models import VesselObservation

SUPPORTED_ATTACKS = frozenset({
    "none",
    "ais_spoofing",
    "transponder_suppression",
    "timestamp_manipulation",
    "spatial_manipulation",
    "combined_evasion",
})


def spoof_position(vessel: VesselObservation, position: tuple[float, float]) -> VesselObservation:
    return replace(vessel, position=position, metadata={**vessel.metadata, "attack": "ais_position_spoofing"})


def suppress_transponder(vessel: VesselObservation) -> VesselObservation:
    return replace(vessel, reported=False, metadata={**vessel.metadata, "attack": "transponder_suppression"})


def manipulate_timestamp(vessel: VesselObservation, offset: float) -> VesselObservation:
    return replace(vessel, timestamp=vessel.timestamp + offset, metadata={**vessel.metadata, "attack": "timestamp_manipulation", "offset": offset})


def manipulate_spatial(vessel: VesselObservation, severity: float) -> VesselObservation:
    """Shift vessel position away from cable by severity-scaled distance."""
    distance = 15.0 * severity
    new_pos = (vessel.position[0] + distance, vessel.position[1] + distance)
    return replace(vessel, position=new_pos, metadata={
        **vessel.metadata,
        "attack": "spatial_manipulation",
        "attack_family": "spatial_manipulation",
        "severity": severity,
        "original_position": vessel.position,
    })


def combined_evasion(vessel: VesselObservation, severity: float) -> VesselObservation:
    """Apply combined spatial shift + timestamp manipulation + position uncertainty inflation."""
    # Spatial shift
    distance = 10.0 * severity
    new_pos = (vessel.position[0] + distance, vessel.position[1] + distance)
    # Timestamp shift
    time_offset = 8.0 * severity
    # Inflate position uncertainty
    new_uncertainty = vessel.position_uncertainty + 5.0 * severity
    return replace(
        vessel,
        position=new_pos,
        timestamp=vessel.timestamp + time_offset,
        position_uncertainty=new_uncertainty,
        metadata={
            **vessel.metadata,
            "attack": "combined_evasion",
            "attack_family": "combined_evasion",
            "severity": severity,
            "original_position": vessel.position,
            "original_timestamp": vessel.timestamp,
            "spatial_shift": distance,
            "time_offset": time_offset,
        },
    )


def apply_attack(vessel: VesselObservation, attack: str, severity: float = 1.0) -> VesselObservation:
    if not 0 <= severity <= 1:
        raise ValueError("severity must be in [0, 1]")
    if attack not in SUPPORTED_ATTACKS:
        raise ValueError(f"unsupported attack: {attack}")
    if severity == 0.0 or attack == "none":
        return vessel
    if attack == "ais_spoofing":
        distance = 10.0 + 20.0 * severity
        return replace(spoof_position(vessel, (distance, distance)), metadata={**vessel.metadata, "attack": "ais_position_spoofing", "attack_family": attack, "severity": severity})
    if attack == "transponder_suppression":
        return replace(suppress_transponder(vessel), metadata={**vessel.metadata, "attack": attack, "severity": severity})
    if attack == "timestamp_manipulation":
        manipulated = manipulate_timestamp(vessel, 10.0 * severity)
        return replace(manipulated, metadata={**manipulated.metadata, "attack_family": attack, "severity": severity})
    if attack == "spatial_manipulation":
        return manipulate_spatial(vessel, severity)
    if attack == "combined_evasion":
        return combined_evasion(vessel, severity)
    return vessel
