from __future__ import annotations

import math

from .models import Association, VesselObservation


def spatial_association(distance: float, interaction_radius: float, position_uncertainty: float = 0.0) -> float:
    if distance < 0 or interaction_radius <= 0 or position_uncertainty < 0:
        raise ValueError("distance and uncertainty must be non-negative; radius must be positive")
    effective_radius = interaction_radius + position_uncertainty
    return float(max(0.0, 1.0 - distance / effective_radius))


def temporal_association(time_offset: float, tolerance: float, timestamp_uncertainty: float = 0.0) -> float:
    if time_offset < 0 or tolerance <= 0 or timestamp_uncertainty < 0:
        raise ValueError("time offset and uncertainty must be non-negative; tolerance must be positive")
    effective_tolerance = tolerance + timestamp_uncertainty
    return float(max(0.0, 1.0 - time_offset / effective_tolerance))


def behaviour_confidence(vessel: VesselObservation, distance: float, interaction_radius: float) -> float:
    proximity = spatial_association(distance, interaction_radius, vessel.position_uncertainty)
    speed_factor = 1.0 if vessel.speed > 0 else 0.4
    return float(min(1.0, proximity * speed_factor))


def associate(
    vessel: VesselObservation,
    disturbance_time: float,
    distance: float,
    *,
    interaction_radius: float,
    temporal_tolerance: float,
    spatial_weight: float = 0.34,
    temporal_weight: float = 0.33,
    behaviour_weight: float = 0.33,
) -> Association:
    weights = (spatial_weight, temporal_weight, behaviour_weight)
    if any(weight < 0 for weight in weights) or not math.isclose(sum(weights), 1.0, abs_tol=1e-9):
        raise ValueError("association weights must be non-negative and sum to one")
    spatial = spatial_association(distance, interaction_radius, vessel.position_uncertainty)
    offset = abs(vessel.timestamp - disturbance_time)
    temporal = temporal_association(offset, temporal_tolerance)
    behaviour = behaviour_confidence(vessel, distance, interaction_radius)
    explanation = []
    if spatial < 0.5:
        explanation.append("vessel outside strong interaction region")
    if temporal < 0.5:
        explanation.append("vessel and disturbance are weakly time-aligned")
    if not vessel.reported:
        explanation.append("no reported vessel corroboration")
    return Association(spatial, temporal, behaviour, distance, offset, tuple(explanation))
