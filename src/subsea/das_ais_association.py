"""DAS/AIS spatial-temporal association pipeline.

This module builds the association pathway:
  DAS event → features → cable geometry → AIS trajectory →
  spatial association → temporal association → behaviour →
  uncertainty → competing hypotheses → decision

Output distinguishes association evidence from causal attribution.
Real DAS data may validate spatial/temporal association but must NOT
be interpreted as confirmed causal cable damage.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from .ais import AisPoint
from .association import associate
from .geometry import Point, Polyline, distance_to_polyline
from .models import Association, DecisionResult, VesselObservation


@dataclass(frozen=True)
class DasEvent:
    """A detected event from DAS signal processing."""
    timestamp: float
    cable_position_km: float
    amplitude: float
    features: dict[str, float]
    channel_index: int = 0


@dataclass(frozen=True)
class AssociationResult:
    """Result of associating a DAS event with an AIS vessel track.

    IMPORTANT: This represents association evidence, NOT causal attribution.
    """
    das_event: DasEvent
    vessel_id: str | None
    association: Association | None
    decision: str  # Association strength label, not causal conclusion
    cable_distance: float | None
    is_causal_claim: bool = False  # Always False for real data
    provenance: dict[str, Any] | None = None


def ais_point_to_vessel_observation(point: AisPoint) -> VesselObservation:
    """Convert an AIS point to a VesselObservation for the pipeline."""
    return VesselObservation(
        vessel_id=point.vessel_id or "unknown",
        timestamp=point.timestamp,
        position=(point.latitude, point.longitude),
        speed=point.speed if point.speed is not None else 0.0,
        heading=point.heading if point.heading is not None else 0.0,
        reported=point.reported,
        position_uncertainty=point.position_uncertainty,
    )


def find_nearest_ais(
    event_timestamp: float,
    ais_points: Sequence[AisPoint],
    *,
    max_time_offset: float = 300.0,
) -> AisPoint | None:
    """Find the AIS point nearest in time to a DAS event."""
    if not ais_points:
        return None
    best = min(ais_points, key=lambda p: abs(p.timestamp - event_timestamp))
    if abs(best.timestamp - event_timestamp) > max_time_offset:
        return None
    return best


def associate_das_ais(
    event: DasEvent,
    ais_points: Sequence[AisPoint],
    cable: Polyline,
    *,
    interaction_radius: float = 10.0,
    temporal_tolerance: float = 60.0,
    max_time_offset: float = 300.0,
) -> AssociationResult:
    """Associate a DAS event with the nearest AIS vessel track.

    This produces association evidence only. It does NOT produce
    causal attribution claims.
    """
    if len(cable) < 2:
        raise ValueError("cable geometry requires at least two points")

    nearest = find_nearest_ais(event.timestamp, ais_points, max_time_offset=max_time_offset)

    if nearest is None:
        return AssociationResult(
            das_event=event,
            vessel_id=None,
            association=None,
            decision="no_vessel_in_window",
            cable_distance=None,
            is_causal_claim=False,
        )

    vessel_obs = ais_point_to_vessel_observation(nearest)
    cable_dist = distance_to_polyline(vessel_obs.position, cable)

    assoc = associate(
        vessel_obs,
        event.timestamp,
        cable_dist,
        interaction_radius=interaction_radius,
        temporal_tolerance=temporal_tolerance,
    )

    # Label by association strength, NOT causal conclusion
    if assoc.confidence >= 0.7:
        label = "strong_association"
    elif assoc.confidence >= 0.4:
        label = "moderate_association"
    elif assoc.confidence > 0.0:
        label = "weak_association"
    else:
        label = "no_association"

    return AssociationResult(
        das_event=event,
        vessel_id=nearest.vessel_id,
        association=assoc,
        decision=label,
        cable_distance=cable_dist,
        is_causal_claim=False,
        provenance={
            "ais_timestamp": nearest.timestamp,
            "ais_position": (nearest.latitude, nearest.longitude),
            "cable_distance": cable_dist,
            "time_offset": abs(nearest.timestamp - event.timestamp),
            "association_confidence": assoc.confidence,
            "note": "Association evidence only. Not causal attribution.",
        },
    )


def associate_all_vessels(
    event: DasEvent,
    ais_points: Sequence[AisPoint],
    cable: Polyline,
    *,
    interaction_radius: float = 10.0,
    temporal_tolerance: float = 60.0,
    max_time_offset: float = 300.0,
) -> list[AssociationResult]:
    """Associate a DAS event with ALL vessels in the AIS data."""
    if not ais_points:
        return [AssociationResult(
            das_event=event, vessel_id=None, association=None,
            decision="no_vessels_available", cable_distance=None,
            is_causal_claim=False,
        )]

    # Group AIS points by vessel
    vessels: dict[str | None, list[AisPoint]] = {}
    for p in ais_points:
        vessels.setdefault(p.vessel_id, []).append(p)

    results = []
    for vid, points in vessels.items():
        result = associate_das_ais(
            event, points, cable,
            interaction_radius=interaction_radius,
            temporal_tolerance=temporal_tolerance,
            max_time_offset=max_time_offset,
        )
        results.append(result)

    return sorted(results, key=lambda r: (r.association.confidence if r.association else 0.0), reverse=True)
