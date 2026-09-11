from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable


@dataclass(frozen=True)
class AisPoint:
    timestamp: float
    latitude: float
    longitude: float
    speed: float | None
    heading: float | None
    vessel_id: str | None = None
    vessel_type: str | None = None
    position_uncertainty: float = 0.0
    reported: bool = True


def _timestamp(value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError("AIS timestamp must be numeric or timezone-aware")
    if isinstance(value, (int, float)):
        result = float(value)
    elif isinstance(value, str):
        try:
            result = float(value)
        except ValueError:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                raise ValueError("AIS timestamp must include an explicit timezone")
            result = parsed.timestamp()
    else:
        raise ValueError("AIS timestamp has unsupported type")
    if not math.isfinite(result):
        raise ValueError("AIS timestamp must be finite")
    return result


def _finite(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"AIS {field} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"AIS {field} must be finite")
    return result


def load_ais_records(records: Iterable[dict[str, Any]], *, interpolate: bool = False) -> tuple[AisPoint, ...]:
    if interpolate:
        raise ValueError("AIS interpolation requires an explicit trajectory policy")
    points: list[AisPoint] = []
    for record in records:
        if "timestamp" not in record or "latitude" not in record or "longitude" not in record:
            raise ValueError("AIS records require timestamp, latitude, and longitude")
        latitude = _finite(record["latitude"], "latitude")
        longitude = _finite(record["longitude"], "longitude")
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise ValueError("AIS latitude/longitude is out of range")
        speed = None if record.get("speed") is None else _finite(record["speed"], "speed")
        uncertainty = _finite(record.get("position_uncertainty", 0.0), "position_uncertainty")
        if speed is not None and speed < 0 or uncertainty < 0:
            raise ValueError("AIS speed and position_uncertainty must be non-negative")
        heading = None if record.get("heading") is None else _finite(record["heading"], "heading")
        if heading is not None and not 0 <= heading < 360:
            raise ValueError("AIS heading must be in [0, 360)")
        reported = record.get("reported", True)
        if not isinstance(reported, bool):
            raise ValueError("AIS reported must be boolean")
        points.append(AisPoint(
            timestamp=_timestamp(record["timestamp"]),
            latitude=latitude,
            longitude=longitude,
            speed=speed,
            heading=heading,
            vessel_id=record.get("vessel_id"),
            vessel_type=record.get("vessel_type"),
            position_uncertainty=uncertainty,
            reported=reported,
        ))
    return tuple(sorted(points, key=lambda point: point.timestamp))
