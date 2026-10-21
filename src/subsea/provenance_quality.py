"""Data Provenance and Quality Validation Module for AbyssLink / SUBSEA.

Enforces strict boundaries between PHYSICAL and SIMULATED sensor channels,
prevents silent data corruption or masquerading, and provides granular
quality assessment (GOOD, DEGRADED, STALE, INVALID, MISSING, OUT_OF_RANGE, CONTRADICTORY).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class DataSource(StrEnum):
    PHYSICAL = "PHYSICAL"
    SIMULATED = "SIMULATED"


class DataQuality(StrEnum):
    GOOD = "GOOD"
    DEGRADED = "DEGRADED"
    STALE = "STALE"
    INVALID = "INVALID"
    MISSING = "MISSING"
    OUT_OF_RANGE = "OUT_OF_RANGE"
    CONTRADICTORY = "CONTRADICTORY"


class OperatingMode(StrEnum):
    PHYSICAL_ONLY = "PHYSICAL_ONLY"
    HYBRID_DEMO = "HYBRID_DEMO"


# Configurable physiological/physical validity boundaries
CHANNEL_BOUNDS: dict[str, tuple[float, float, str]] = {
    "ultrasonic_distance": (0.02, 5.0, "m"),          # HC-SR04 benchtop 2cm to 500cm in air
    "vessel_distance": (0.0, 5000.0, "m"),            # Virtual vessel proximity to cable
    "vessel_speed": (0.0, 50.0, "m/s"),               # Vessel speed
    "vibration_acceleration": (-20.0, 20.0, "g"),     # Triaxial / magnitude acceleration
    "das_rms": (0.0, 100.0, "units"),                 # DAS spectral acoustic RMS
    "seafloor_temperature": (-3.0, 40.0, "deg_c"),    # Subsea benthic temperature
    "cable_strain": (-3000.0, 3000.0, "microstrain"), # Optical strain gauge
    "cable_health_index": (0.0, 1.0, "ratio"),        # Condition index [0, 1]
    "optical_transmission": (0.0, 1.0, "state"),      # Binary state flag 0 or 1
}


@dataclass(frozen=True)
class SensorReading:
    """A standardized, provenance-tagged sensor measurement or feature reading."""
    sensor_id: str
    source: DataSource
    timestamp: float
    value: Any
    unit: str
    quality: DataQuality = DataQuality.GOOD
    scenario_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["source"] = self.source.value
        d["quality"] = self.quality.value
        return d

    @property
    def is_usable(self) -> bool:
        """Indicates if reading represents trustworthy data for warning decisions."""
        return self.quality in (DataQuality.GOOD, DataQuality.DEGRADED)

    @property
    def is_physical(self) -> bool:
        return self.source == DataSource.PHYSICAL

    @property
    def is_simulated(self) -> bool:
        return self.source == DataSource.SIMULATED


class DataQualityValidator:
    """Validates individual readings and time-series for quality and integrity."""

    def __init__(
        self,
        stale_threshold_s: float = 2.0,
        bounds: dict[str, tuple[float, float, str]] | None = None,
    ) -> None:
        self.stale_threshold_s = stale_threshold_s
        self.bounds = bounds or CHANNEL_BOUNDS
        self._last_timestamps: dict[str, float] = {}

    def validate_reading(
        self,
        reading: SensorReading,
        now: float | None = None,
    ) -> SensorReading:
        """Examines a SensorReading against bounds, freshness, and structural rules.

        Returns a new SensorReading with updated quality status and reasons in metadata.
        Never converts missing or invalid readings into healthy values.
        """
        reasons: list[str] = list(reading.metadata.get("quality_reasons", []))
        quality = reading.quality

        # 1. Missing or Null Value Check
        if reading.value is None:
            quality = DataQuality.MISSING
            reasons.append("Value is null or unavailable")
            new_meta = {**reading.metadata, "quality_reasons": reasons}
            return SensorReading(
                sensor_id=reading.sensor_id,
                source=reading.source,
                timestamp=reading.timestamp,
                value=None,
                unit=reading.unit,
                quality=quality,
                scenario_id=reading.scenario_id,
                metadata=new_meta,
            )

        # 2. Timestamp Validation (Monotonicity & Duplicates)
        last_t = self._last_timestamps.get(reading.sensor_id)
        if last_t is not None:
            if reading.timestamp < last_t:
                quality = DataQuality.INVALID
                reasons.append(f"Timestamp decreased (backwards drift: {reading.timestamp} < {last_t})")
            elif reading.timestamp == last_t:
                quality = DataQuality.DEGRADED
                reasons.append(f"Duplicate timestamp detected ({reading.timestamp})")

        self._last_timestamps[reading.sensor_id] = reading.timestamp

        # 3. Freshness / Stale Check
        if now is not None and (now - reading.timestamp) > self.stale_threshold_s:
            quality = DataQuality.STALE
            reasons.append(f"Data is stale (age: {now - reading.timestamp:.2f}s > {self.stale_threshold_s}s)")

        # 4. Out-of-Range Bounds Check
        if reading.sensor_id in self.bounds and isinstance(reading.value, (int, float)):
            low, high, _ = self.bounds[reading.sensor_id]
            if not (low <= float(reading.value) <= high):
                quality = DataQuality.OUT_OF_RANGE
                reasons.append(f"Value {reading.value} outside physical bounds [{low}, {high}]")

        # 5. Contradiction Checks
        if reading.sensor_id == "optical_link":
            # Example: optical beam broken while laser is declared OFF is not a link fault
            laser_state = reading.metadata.get("laser", "OFF")
            ldr_val = reading.metadata.get("ldr", 0)
            if laser_state == "OFF" and ldr_val == 1 and reading.value == "FAULT":
                quality = DataQuality.CONTRADICTORY
                reasons.append("Link fault claimed while laser is unpowered")

        new_meta = {**reading.metadata, "quality_reasons": reasons}
        return SensorReading(
            sensor_id=reading.sensor_id,
            source=reading.source,
            timestamp=reading.timestamp,
            value=reading.value,
            unit=reading.unit,
            quality=quality,
            scenario_id=reading.scenario_id,
            metadata=new_meta,
        )

    def reset(self) -> None:
        """Reset historical timestamp trackers."""
        self._last_timestamps.clear()
