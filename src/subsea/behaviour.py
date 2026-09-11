from __future__ import annotations

import math
from collections.abc import Sequence

from .geometry import Point, Polyline, distance_confidence, distance_to_polyline
from .trajectory import closest_point_of_approach, crossing_detected, dwell_time


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _angle_difference(left: float, right: float) -> float:
    return abs((left - right + 180.0) % 360.0 - 180.0)


def behaviour_components(
    trajectory: Sequence[Point],
    timestamps: Sequence[float],
    cable: Polyline,
    *,
    speeds: Sequence[float | None],
    headings: Sequence[float | None],
    interaction_radius: float,
) -> dict[str, float]:
    if len(trajectory) != len(timestamps) or len(trajectory) != len(speeds) or len(trajectory) != len(headings) or not trajectory:
        raise ValueError("trajectory, timestamps, speeds, and headings must be equal and non-empty")
    if interaction_radius <= 0:
        raise ValueError("interaction_radius must be positive")
    distances = [distance_to_polyline(point, cable) for point in trajectory]
    cpa, _ = closest_point_of_approach(trajectory, cable)
    proximity = distance_confidence(sum(distances) / len(distances), interaction_radius)
    dwell = _clamp(dwell_time(trajectory, timestamps, cable, radius=interaction_radius) / max(timestamps[-1] - timestamps[0], 1e-12))
    crossing = 1.0 if crossing_detected(trajectory, cable) else 0.0
    valid_speeds = [float(value) for value in speeds if value is not None and math.isfinite(float(value))]
    speed = _clamp((sum(valid_speeds) / len(valid_speeds)) / 10.0) if valid_speeds else 0.0
    valid_headings = [float(value) for value in headings if value is not None and math.isfinite(float(value))]
    heading = _clamp(1.0 - min(_angle_difference(valid_headings[-1], 90.0), 180.0) / 180.0) if valid_headings else 0.0
    if len(trajectory) >= 2:
        motion_x = trajectory[-1][0] - trajectory[0][0]
        motion_y = trajectory[-1][1] - trajectory[0][1]
        approach_direction = _clamp(abs(motion_y) / max(math.hypot(motion_x, motion_y), 1e-12))
    else:
        approach_direction = 0.0
    return {"proximity": proximity, "approach_direction": approach_direction, "speed": speed, "heading": heading, "dwell": dwell, "crossing": crossing, "cpa": distance_confidence(cpa, interaction_radius)}
