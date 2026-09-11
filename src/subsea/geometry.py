from __future__ import annotations

import math
from collections.abc import Sequence

Point = tuple[float, float]
Polyline = Sequence[Point]


def _distance(left: Point, right: Point) -> float:
    return math.hypot(left[0] - right[0], left[1] - right[1])


def nearest_point_on_polyline(point: Point, polyline: Polyline) -> tuple[Point, float]:
    if len(polyline) < 2:
        raise ValueError("polyline requires at least two points")
    try:
        valid_shape = len(point) == 2 and all(len(candidate) == 2 for candidate in polyline)
        finite = all(math.isfinite(float(value)) for coordinate in (point, *polyline) for value in coordinate)
    except (TypeError, ValueError):
        raise ValueError("geometry points must be finite 2D coordinates") from None
    if not valid_shape or not finite:
        raise ValueError("geometry points must contain exactly two coordinates")
    best_point = polyline[0]
    best_distance = math.inf
    for start, end in zip(polyline[:-1], polyline[1:]):
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        length_squared = dx * dx + dy * dy
        if length_squared == 0:
            candidate = start
        else:
            scale = ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / length_squared
            scale = max(0.0, min(1.0, scale))
            candidate = (start[0] + scale * dx, start[1] + scale * dy)
        candidate_distance = _distance(point, candidate)
        if candidate_distance < best_distance:
            best_point, best_distance = candidate, candidate_distance
    return best_point, best_distance


def distance_to_polyline(point: Point, polyline: Polyline) -> float:
    return nearest_point_on_polyline(point, polyline)[1]


def distance_confidence(distance: float, interaction_radius: float, position_uncertainty: float = 0.0) -> float:
    if distance < 0 or interaction_radius <= 0 or position_uncertainty < 0:
        raise ValueError("distance and uncertainty must be non-negative; radius must be positive")
    return max(0.0, min(1.0, 1.0 - distance / (interaction_radius + position_uncertainty)))
