"""Digital Twin Simulation Module for Subsea Cable Monitoring.

Generates repeatable, physics-inspired software channels for subsea disturbance assessment:
- DAS-like vibrational features and acoustics
- Virtual vessel kinematics and proximity
- Virtual seafloor benthic temperature
- Virtual mechanical cable strain and condition index

Scientific Integrity Notice:
All channels produced by this module are marked as DataSource.SIMULATED.
They represent mathematical benchmark models for system evaluation and are not
measurements from real field DAS or marine sensors.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
import math
import random
from typing import Any

import numpy as np

from .provenance_quality import DataQuality, DataSource, SensorReading


class TwinScenario(StrEnum):
    NORMAL_OPERATION = "normal_operation"
    APPROACHING_VESSEL = "approaching_vessel"
    LOW_LEVEL_VIBRATION = "low_level_vibration"
    INCREASING_DISTURBANCE = "increasing_disturbance"
    SEVERE_DISTURBANCE = "severe_disturbance"
    SENSOR_DEGRADATION = "sensor_degradation"
    RECOVERY = "recovery"


SCENARIO_GROUND_TRUTH: dict[TwinScenario, dict[str, Any]] = {
    TwinScenario.NORMAL_OPERATION: {"t_event": None, "event_description": "Nominal operations: no disturbance"},
    TwinScenario.APPROACHING_VESSEL: {"t_event": 15.9, "event_description": "Vessel approaches interaction corridor (<15m)"},
    TwinScenario.LOW_LEVEL_VIBRATION: {"t_event": 0.3, "event_description": "Subtle vibration anomaly onset"},
    TwinScenario.INCREASING_DISTURBANCE: {"t_event": 15.0, "event_description": "Ramp to persistent critical disturbance"},
    TwinScenario.SEVERE_DISTURBANCE: {"t_event": 1.5, "event_description": "Direct anchor/trawl strike event"},
    TwinScenario.SENSOR_DEGRADATION: {"t_event": 6.0, "event_description": "Telemetry degradation and stale channel fault"},
    TwinScenario.RECOVERY: {"t_event": 0.0, "event_description": "Exponential disturbance decay and recovery"},
}



@dataclass(frozen=True)
class DigitalTwinFrame:
    """A synchronized multi-channel telemetry snapshot from the Digital Twin."""
    scenario_id: str
    timestamp: float
    elapsed_s: float
    phase: str
    readings: dict[str, SensorReading]
    summary: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "timestamp": self.timestamp,
            "elapsed_s": round(self.elapsed_s, 2),
            "phase": self.phase,
            "readings": {k: v.to_dict() for k, v in self.readings.items()},
            "summary": self.summary,
        }


class DigitalTwinSimulator:
    """Stateful digital twin simulator with deterministic scenario generation."""

    def __init__(self, seed: int = 42, base_time: float = 1000.0) -> None:
        self.master_seed = seed
        self.base_time = base_time
        self.current_scenario: TwinScenario = TwinScenario.NORMAL_OPERATION
        self.elapsed_s: float = 0.0
        self.rng = np.random.RandomState(seed)

        # Cable is modeled lying along the Y-axis (X = 0)
        self.cable_x = 0.0

        # State memory for smooth temporal evolution
        self.vessel_x = 200.0
        self.vessel_y = 50.0
        self.vessel_speed = 0.0
        self.vessel_heading = 0.0
        self.temperature = 4.0
        self.strain = 0.0
        self.condition_index = 1.0
        self.vibration_rms = 0.08
        self.phase = "NORMAL"

    @property
    def ground_truth_t_event(self) -> float | None:
        """Returns the ground-truth disturbance event onset time in elapsed seconds, if applicable."""
        info = SCENARIO_GROUND_TRUTH.get(self.current_scenario)
        return info.get("t_event") if info else None

    def set_scenario(self, scenario: TwinScenario | str, seed: int | None = None) -> None:
        """Configures and resets the simulator state for a specific scenario."""
        if isinstance(scenario, str):
            scenario = TwinScenario(scenario)
        self.current_scenario = scenario
        self.elapsed_s = 0.0

        use_seed = seed if seed is not None else self.master_seed
        self.rng = np.random.RandomState(use_seed)

        # Initial scenario configurations
        if scenario == TwinScenario.NORMAL_OPERATION:
            self.vessel_x = 350.0
            self.vessel_y = 100.0
            self.vessel_speed = 6.0
            self.vessel_heading = 45.0
            self.temperature = 4.0
            self.strain = 5.0
            self.condition_index = 0.99
            self.vibration_rms = 0.08
            self.phase = "NORMAL"

        elif scenario == TwinScenario.APPROACHING_VESSEL:
            self.vessel_x = 80.0
            self.vessel_y = -40.0
            self.vessel_speed = 3.5
            self.vessel_heading = 180.0 # Heading toward X=0
            self.temperature = 4.0
            self.strain = 10.0
            self.condition_index = 0.98
            self.vibration_rms = 0.10
            self.phase = "APPROACHING"

        elif scenario == TwinScenario.LOW_LEVEL_VIBRATION:
            self.vessel_x = 180.0
            self.vessel_y = 30.0
            self.vessel_speed = 3.0
            self.vessel_heading = 90.0
            self.temperature = 4.0
            self.strain = 20.0
            self.condition_index = 0.96
            self.vibration_rms = 0.35
            self.phase = "ANOMALY_ONSET"

        elif scenario == TwinScenario.INCREASING_DISTURBANCE:
            self.vessel_x = 35.0
            self.vessel_y = -10.0
            self.vessel_speed = 2.0
            self.vessel_heading = 180.0
            self.temperature = 4.2
            self.strain = 80.0
            self.condition_index = 0.85
            self.vibration_rms = 0.55
            self.phase = "ESCALATING"

        elif scenario == TwinScenario.SEVERE_DISTURBANCE:
            self.vessel_x = 10.0
            self.vessel_y = 5.0
            self.vessel_speed = 1.0
            self.vessel_heading = 180.0
            self.temperature = 4.8
            self.strain = 380.0
            self.condition_index = 0.35
            self.vibration_rms = 2.40
            self.phase = "CRITICAL_DISTURBANCE"

        elif scenario == TwinScenario.SENSOR_DEGRADATION:
            self.vessel_x = 120.0
            self.vessel_y = 40.0
            self.vessel_speed = 2.0
            self.vessel_heading = 0.0
            self.temperature = 4.0
            self.strain = 8.0
            self.condition_index = 0.98
            self.vibration_rms = 0.08
            self.phase = "DEGRADATION_TRIGGERED"

        elif scenario == TwinScenario.RECOVERY:
            self.vessel_x = 15.0
            self.vessel_y = 0.0
            self.vessel_speed = 3.5
            self.vessel_heading = 0.0 # Moving away from cable
            self.temperature = 4.6
            self.strain = 200.0
            self.condition_index = 0.60
            self.vibration_rms = 1.20
            self.phase = "DE_ESCALATING"

    def step(self, dt: float = 0.3) -> DigitalTwinFrame:
        """Advances the simulation by dt seconds and returns a synchronized frame."""
        self.elapsed_s += dt
        t = self.base_time + self.elapsed_s
        scen = self.current_scenario
        q_default = DataQuality.GOOD

        # 1. Update Kinematics and Vessel Proximity
        if scen == TwinScenario.NORMAL_OPERATION:
            # Transit parallel to cable at safe distance (>200m)
            self.vessel_y += self.vessel_speed * dt
            self.vessel_x += 0.05 * math.sin(self.elapsed_s * 0.1)
            dist_to_cable = abs(self.vessel_x - self.cable_x)
            self.vibration_rms = 0.08 + float(self.rng.normal(0, 0.01))
            self.temperature = 4.0 + float(self.rng.normal(0, 0.02))
            self.strain = 5.0 + float(self.rng.normal(0, 0.5))
            self.condition_index = 0.99
            self.phase = "NORMAL"

        elif scen == TwinScenario.APPROACHING_VESSEL:
            # Steady advance toward cable from 150m down to 12m
            if self.vessel_x > 12.0:
                self.vessel_x = max(12.0, self.vessel_x - self.vessel_speed * dt)
            self.vessel_y += 0.5 * dt
            dist_to_cable = abs(self.vessel_x - self.cable_x)
            # Acoustic excitation rises inversely with proximity
            self.vibration_rms = 0.10 + (15.0 / max(10.0, dist_to_cable)) * 0.25 + float(self.rng.normal(0, 0.02))
            self.temperature = 4.0 + float(self.rng.normal(0, 0.02))
            self.strain = 10.0 + (30.0 / max(5.0, dist_to_cable))
            self.condition_index = max(0.90, 1.0 - (20.0 / dist_to_cable) * 0.05)
            self.phase = "APPROACHING" if dist_to_cable > 25.0 else "INTERACTION_ZONE"

        elif scen == TwinScenario.LOW_LEVEL_VIBRATION:
            # Slow transit, elevated vibration baseline
            self.vessel_y += self.vessel_speed * dt
            dist_to_cable = abs(self.vessel_x - self.cable_x)
            self.vibration_rms = 0.38 + 0.08 * math.sin(self.elapsed_s * 1.5) + float(self.rng.normal(0, 0.03))
            self.temperature = 4.15 + float(self.rng.normal(0, 0.03))
            self.strain = 25.0 + 5.0 * math.sin(self.elapsed_s * 0.8)
            self.condition_index = 0.94
            self.phase = "ANOMALY_ONSET"

        elif scen == TwinScenario.INCREASING_DISTURBANCE:
            # Vessel enters 10m corridor, vibration ramps up
            if self.vessel_x > 6.0:
                self.vessel_x = max(6.0, self.vessel_x - 1.2 * dt)
            dist_to_cable = abs(self.vessel_x - self.cable_x)
            ramp = min(1.0, self.elapsed_s / 20.0)
            self.vibration_rms = 0.30 + ramp * 1.10 + float(self.rng.normal(0, 0.05))
            self.strain = 50.0 + ramp * 180.0
            self.temperature = 4.1 + ramp * 0.5
            self.condition_index = max(0.55, 0.95 - ramp * 0.40)
            self.phase = "ESCALATING" if ramp < 0.8 else "PERSISTENT_DISTURBANCE"

        elif scen == TwinScenario.SEVERE_DISTURBANCE:
            # Dragging speed across cable route (X crossing 0)
            self.vessel_x = 8.0 - (self.elapsed_s * 0.8)
            dist_to_cable = abs(self.vessel_x - self.cable_x)
            burst = 1.0 if abs(dist_to_cable) < 4.0 else 0.4
            self.vibration_rms = 1.80 + burst * 1.2 + float(self.rng.normal(0, 0.1))
            self.strain = 350.0 + burst * 250.0 + float(self.rng.normal(0, 10.0))
            self.temperature = 4.7 + float(self.rng.normal(0, 0.08))
            self.condition_index = max(0.20, 0.45 - (self.elapsed_s * 0.015))
            self.phase = "SEVERE_ANCHOR_TRAWL"

        elif scen == TwinScenario.SENSOR_DEGRADATION:
            # Simulates degraded sensor channels (stale, dropouts, noise)
            dist_to_cable = abs(self.vessel_x - self.cable_x)
            if self.elapsed_s > 6.0:
                q_default = DataQuality.DEGRADED
            if self.elapsed_s > 12.0:
                q_default = DataQuality.STALE
            self.vibration_rms = 0.15 + float(self.rng.normal(0, 0.5)) # High noise
            self.phase = "SENSOR_FAULT_DEGRADATION"

        elif scen == TwinScenario.RECOVERY:
            # Disturbance decays exponentially back to ambient baseline
            decay = math.exp(-self.elapsed_s / 8.0)
            self.vessel_x += (2.5 * dt) # Moving away
            dist_to_cable = abs(self.vessel_x - self.cable_x)
            self.vibration_rms = 0.08 + 1.20 * decay + float(self.rng.normal(0, 0.02))
            self.strain = 10.0 + 220.0 * decay
            self.temperature = 4.0 + 0.6 * decay
            self.condition_index = min(0.98, 0.60 + (1.0 - decay) * 0.35)
            self.phase = "RECOVERING" if decay > 0.15 else "RESTORED_NOMINAL"

        # Safe clamp for physical indicators
        dist_to_cable = max(0.1, abs(self.vessel_x - self.cable_x))
        self.vibration_rms = max(0.01, float(self.vibration_rms))
        self.condition_index = max(0.0, min(1.0, float(self.condition_index)))

        # Assemble Readings Dictionary
        readings: dict[str, SensorReading] = {}

        # 1. Virtual DAS Acoustic / Vibration RMS
        readings["das_rms"] = SensorReading(
            sensor_id="das_rms",
            source=DataSource.SIMULATED,
            timestamp=t,
            value=round(self.vibration_rms, 3),
            unit="units",
            quality=q_default,
            scenario_id=scen.value,
            metadata={"description": "Simulated DAS acoustic spectral band RMS"},
        )

        # 2. Virtual Vessel Distance (Proximity to Cable)
        dist_val = round(dist_to_cable, 1) if scen != TwinScenario.SENSOR_DEGRADATION or self.elapsed_s < 10.0 else None
        readings["vessel_distance"] = SensorReading(
            sensor_id="vessel_distance",
            source=DataSource.SIMULATED,
            timestamp=t,
            value=dist_val,
            unit="m",
            quality=DataQuality.MISSING if dist_val is None else q_default,
            scenario_id=scen.value,
            metadata={
                "vessel_x": round(self.vessel_x, 1),
                "vessel_y": round(self.vessel_y, 1),
                "speed_ms": round(self.vessel_speed, 1),
            },
        )

        # 3. Virtual Seafloor Temperature
        readings["seafloor_temperature"] = SensorReading(
            sensor_id="seafloor_temperature",
            source=DataSource.SIMULATED,
            timestamp=t,
            value=round(self.temperature, 2),
            unit="deg_c",
            quality=q_default,
            scenario_id=scen.value,
            metadata={"nominal_baseline": 4.0},
        )

        # 4. Virtual Cable Strain
        readings["cable_strain"] = SensorReading(
            sensor_id="cable_strain",
            source=DataSource.SIMULATED,
            timestamp=t,
            value=round(self.strain, 1),
            unit="microstrain",
            quality=q_default,
            scenario_id=scen.value,
            metadata={"nominal_threshold": 100.0, "critical_threshold": 300.0},
        )

        # 5. Virtual Cable Condition Index [0.0, 1.0]
        readings["cable_health_index"] = SensorReading(
            sensor_id="cable_health_index",
            source=DataSource.SIMULATED,
            timestamp=t,
            value=round(self.condition_index, 3),
            unit="ratio",
            quality=q_default,
            scenario_id=scen.value,
            metadata={"healthy": 1.0, "compromised": 0.5},
        )

        summary = {
            "vibration_rms": round(self.vibration_rms, 3),
            "distance_m": round(dist_to_cable, 1),
            "temperature_c": round(self.temperature, 2),
            "strain_microstrain": round(self.strain, 1),
            "condition_index": round(self.condition_index, 3),
            "phase": self.phase,
        }

        return DigitalTwinFrame(
            scenario_id=scen.value,
            timestamp=round(t, 2),
            elapsed_s=round(self.elapsed_s, 2),
            phase=self.phase,
            readings=readings,
            summary=summary,
        )

    def generate_scenario(
        self,
        scenario: TwinScenario | str,
        duration_s: float = 30.0,
        dt: float = 0.3,
        seed: int = 42,
    ) -> list[DigitalTwinFrame]:
        """Generates a complete time series sequence of frames for a given scenario."""
        self.set_scenario(scenario, seed=seed)
        frames: list[DigitalTwinFrame] = []
        n_steps = int(round(duration_s / dt))
        for _ in range(n_steps):
            frame = self.step(dt=dt)
            frames.append(frame)
        return frames
