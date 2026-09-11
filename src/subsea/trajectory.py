from __future__ import annotations

import math

from collections.abc import Sequence

from .geometry import Point, Polyline, distance_to_polyline


def closest_point_of_approach(trajectory: Sequence[Point], cable: Polyline) -> tuple[float, int]:
    if not trajectory:
        raise ValueError("trajectory must not be empty")
    distances = [distance_to_polyline(point, cable) for point in trajectory]
    index = min(range(len(distances)), key=distances.__getitem__)
    return distances[index], index


def dwell_time(trajectory: Sequence[Point], timestamps: Sequence[float], cable: Polyline, *, radius: float) -> float:
    if len(trajectory) != len(timestamps) or not trajectory:
        raise ValueError("trajectory and timestamps must be non-empty and equal length")
    if not math.isfinite(radius) or radius <= 0 or any(not math.isfinite(float(timestamp)) for timestamp in timestamps):
        raise ValueError("radius must be positive")
    if any(right < left for left, right in zip(timestamps[:-1], timestamps[1:])):
        raise ValueError("timestamps must be ordered")
    inside = [distance_to_polyline(point, cable) <= radius for point in trajectory]
    durations = [timestamps[index + 1] - timestamps[index] for index in range(len(timestamps) - 1) if inside[index]]
    return float(sum(durations))


def crossing_detected(trajectory: Sequence[Point], cable: Polyline) -> bool:
    try:
        valid_shape = all(len(point) == 2 for point in (*trajectory, *cable))
        finite = all(math.isfinite(float(value)) for point in (*trajectory, *cable) for value in point)
    except (TypeError, ValueError):
        raise ValueError("geometry points must be finite 2D coordinates") from None
    if not valid_shape or not finite:
        raise ValueError("geometry points must be finite 2D coordinates")
    if len(cable) < 2:
        raise ValueError("polyline requires at least two points")
    if len(trajectory) < 2:
        return False
    for previous, current in zip(trajectory[:-1], trajectory[1:]):
        for start, end in zip(cable[:-1], cable[1:]):
            if _segments_cross(previous, current, start, end):
                return True
    return False


def _segments_cross(first_start: Point, first_end: Point, second_start: Point, second_end: Point) -> bool:
    def orientation(a: Point, b: Point, c: Point) -> float:
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    first = orientation(first_start, first_end, second_start)
    second = orientation(first_start, first_end, second_end)
    third = orientation(second_start, second_end, first_start)
    fourth = orientation(second_start, second_end, first_end)
    return first * second < 0 and third * fourth < 0


def signed_side(point: Point, cable: Polyline) -> float:
    if len(cable) < 2:
        raise ValueError("polyline requires at least two points")
    start, end = cable[0], cable[-1]
    return (end[0] - start[0]) * (point[1] - start[1]) - (end[1] - start[1]) * (point[0] - start[0])
