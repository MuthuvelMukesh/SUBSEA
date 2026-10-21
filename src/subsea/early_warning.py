"""Independent Multi-Sensor Early Warning Engine for Subsea Cable Monitoring.

Implements early-warning states (W0, W1, W2, W3, WX) providing advance
situational awareness, complementary to and strictly independent of the
existing T0/T1/T2/T3/TX disturbance classification logic.

Operating Modes:
- PHYSICAL_ONLY: Considers solely validated physical hardware channels.
  Simulated data is strictly ignored and isolated.
- HYBRID_DEMO: Fuses physical telemetry with simulated digital twin channels,
  explicitly tagging data provenance on every reading and decision.

Scientific Integrity Notice:
Simulated channels are benchmarks for algorithmic demonstrator evaluation and
do not represent real field DAS or subsea acoustic measurements.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
import time
from typing import Any

from .provenance_quality import (
    DataQuality,
    DataSource,
    OperatingMode,
    SensorReading,
    DataQualityValidator,
)


class EarlyWarningState(StrEnum):
    W0 = "W0"  # Normal: no warning criteria currently met
    W1 = "W1"  # Watch: initial anomaly or approaching simulated vessel
    W2 = "W2"  # Advisory: multiple supporting indicators or persistent anomaly
    W3 = "W3"  # Urgent: sustained, high-confidence warning criteria met
    WX = "WX"  # Unknown / Data Quality: insufficient, stale, or unreliable evidence


@dataclass
class EarlyWarningThresholds:
    """Configurable thresholds for physical and simulated indicator triggers."""
    # Physical thresholds
    ultrasonic_distance_alert_m: float = 1.5   # Scaled distance indicating proximity
    optical_link_fault_value: int = 1         # LDR interrupted
    vibration_flag_value: int = 1             # Piezo vibration detected

    # Simulated digital twin thresholds
    vessel_distance_watch_m: float = 60.0     # Virtual vessel approaching (<60m)
    vessel_distance_urgent_m: float = 15.0    # Virtual vessel in immediate corridor (<15m)
    das_rms_watch: float = 0.25               # Elevated acoustic background
    das_rms_urgent: float = 1.00              # Strong acoustic disturbance
    cable_strain_watch: float = 40.0          # Elevated mechanical microstrain
    cable_strain_urgent: float = 250.0        # Severe mechanical microstrain
    temperature_delta_watch: float = 0.35     # Thermal deviation from baseline (4.0°C)
    cable_health_advisory: float = 0.85       # Degraded condition index (<0.85)
    cable_health_urgent: float = 0.50         # Severely degraded condition index (<0.50)

    # Persistence & Hysteresis settings
    persistence_advisory_frames: int = 3      # Consecutive frames for W1 -> W2 escalation
    persistence_urgent_frames: int = 5        # Consecutive frames for W2 -> W3 escalation
    deescalation_quiet_frames: int = 4        # Consecutive quiet frames to step down


@dataclass(frozen=True)
class EarlyWarningDecision:
    """A structured, explainable early warning decision output."""
    state: EarlyWarningState
    mode: OperatingMode
    confidence: float
    triggering_indicators: tuple[str, ...]
    evidence_sources: dict[str, str]           # sensor_id -> DataSource string (PHYSICAL / SIMULATED)
    data_quality: DataQuality
    explanation: str
    timestamp: float
    scenario_id: str | None = None
    reasons: tuple[str, ...] = ()
    active_indicators_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "mode": self.mode.value,
            "confidence": round(self.confidence, 4),
            "triggering_indicators": list(self.triggering_indicators),
            "evidence_sources": self.evidence_sources,
            "data_quality": self.data_quality.value,
            "explanation": self.explanation,
            "timestamp": round(self.timestamp, 3),
            "scenario_id": self.scenario_id,
            "reasons": list(self.reasons),
            "active_indicators_count": self.active_indicators_count,
            "metadata": self.metadata,
        }


class EarlyWarningEngine:
    """Multi-sensor early-warning state machine with persistence and provenance tracking."""

    def __init__(
        self,
        thresholds: EarlyWarningThresholds | None = None,
        validator: DataQualityValidator | None = None,
    ) -> None:
        self.thresholds = thresholds or EarlyWarningThresholds()
        self.validator = validator or DataQualityValidator()
        self.current_state: EarlyWarningState = EarlyWarningState.W0
        self.anomaly_streak: int = 0
        self.quiet_streak: int = 0
        self._history: list[EarlyWarningDecision] = []

    def reset(self) -> None:
        """Resets the state machine and streak counters to initial normal state."""
        self.current_state = EarlyWarningState.W0
        self.anomaly_streak = 0
        self.quiet_streak = 0
        self.validator.reset()
        self._history.clear()

    def evaluate(
        self,
        readings: dict[str, SensorReading],
        mode: OperatingMode = OperatingMode.HYBRID_DEMO,
        timestamp: float | None = None,
        scenario_id: str | None = None,
    ) -> EarlyWarningDecision:
        """Evaluates sensor readings and produces a structured early warning decision.

        Enforces:
        - Strict isolation in PHYSICAL_ONLY mode: simulated channels are filtered out.
        - Provenance tracking in HYBRID_DEMO mode: each channel source is logged.
        - Multi-indicator corroboration: single synthetic signal never jumps to W2/W3 alone.
        - Fail-safe WX state on stale, corrupt, or insufficient sensor evidence.
        - Hysteresis to prevent alarm flickering.
        """
        # Resolve timestamp for freshness / stale evaluation
        if timestamp is not None:
            now = timestamp
        elif readings:
            # Default to latest timestamp in batch for simulation/replay consistency
            now = max((r.timestamp for r in readings.values() if r.timestamp is not None), default=time.time())
        else:
            now = time.time()

        th = self.thresholds

        # 1. Validate and filter readings based on operating mode
        validated_readings: dict[str, SensorReading] = {}
        for s_id, r in readings.items():
            val_r = self.validator.validate_reading(r, now=now)
            if mode == OperatingMode.PHYSICAL_ONLY:
                # Physical-only mode strictly rejects simulated channels
                if val_r.source == DataSource.PHYSICAL:
                    validated_readings[s_id] = val_r
            else:
                validated_readings[s_id] = val_r

        # Map evidence sources for audit trail
        evidence_sources = {
            s_id: r.source.value for s_id, r in validated_readings.items()
        }

        # 2. Assess Data Quality Health
        data_quality = DataQuality.GOOD
        quality_issues: list[str] = []

        if not validated_readings:
            data_quality = DataQuality.MISSING
            if mode == OperatingMode.PHYSICAL_ONLY:
                quality_issues.append("Physical hardware disconnected: no physical channels available")
            else:
                quality_issues.append("No usable sensor channels available for mode")
        else:
            for s_id, r in validated_readings.items():
                if r.quality in (DataQuality.INVALID, DataQuality.OUT_OF_RANGE, DataQuality.CONTRADICTORY):
                    data_quality = r.quality
                    quality_issues.append(f"{s_id}: {r.quality.value} ({r.metadata.get('quality_reasons')})")
                elif r.quality == DataQuality.STALE and data_quality != DataQuality.INVALID:
                    data_quality = DataQuality.STALE
                    quality_issues.append(f"{s_id} is stale")
                elif r.quality == DataQuality.MISSING and data_quality not in (DataQuality.INVALID, DataQuality.STALE):
                    data_quality = DataQuality.MISSING
                    quality_issues.append(f"{s_id} is missing")
                elif r.quality == DataQuality.DEGRADED and data_quality == DataQuality.GOOD:
                    data_quality = DataQuality.DEGRADED

        # 3. Check for Fail-Safe WX Condition
        # If critical quality issues exist (missing channels, stale, invalid, contradictory), transition to WX
        if data_quality in (DataQuality.MISSING, DataQuality.INVALID, DataQuality.CONTRADICTORY, DataQuality.STALE):
            self.current_state = EarlyWarningState.WX
            self.anomaly_streak = 0
            self.quiet_streak = 0
            dec = EarlyWarningDecision(
                state=EarlyWarningState.WX,
                mode=mode,
                confidence=0.0,
                triggering_indicators=(),
                evidence_sources=evidence_sources,
                data_quality=data_quality,
                explanation="Early warning suspended: unreliable, stale, missing, or contradictory data.",
                timestamp=now,
                scenario_id=scenario_id,
                reasons=tuple(quality_issues),
                active_indicators_count=0,
                metadata={"quality_issues": quality_issues},
            )
            self._history.append(dec)
            return dec

        # 4. Extract Triggering Indicators from Usable Channels
        indicators: list[str] = []
        indicator_groups: set[str] = set() # Groups to prevent correlated false escalation

        for s_id, r in validated_readings.items():
            if not r.is_usable:
                continue

            v = r.value

            # Physical Ultrasonic Distance
            if s_id == "ultrasonic_distance" and isinstance(v, (int, float)):
                if v <= th.ultrasonic_distance_alert_m:
                    indicators.append(f"Physical ultrasonic target proximity ({v:.2f} m <= {th.ultrasonic_distance_alert_m} m)")
                    indicator_groups.add("proximity")

            # Physical Piezo Vibration
            elif s_id == "piezo_vibration" and isinstance(v, (int, float)):
                if int(v) == th.vibration_flag_value:
                    indicators.append("Physical piezo vibration flag active")
                    indicator_groups.add("vibration")

            # Physical Optical Link (LDR)
            elif s_id == "optical_link":
                if (isinstance(v, int) and v == th.optical_link_fault_value) or v in ("FAULT", "BROKEN"):
                    indicators.append("Physical optical link interrupted (LDR fault)")
                    indicator_groups.add("optical_link")

            # Simulated Virtual Vessel Proximity
            elif s_id == "vessel_distance" and isinstance(v, (int, float)):
                if v <= th.vessel_distance_urgent_m:
                    indicators.append(f"Simulated vessel in critical corridor ({v:.1f} m <= {th.vessel_distance_urgent_m} m)")
                    indicator_groups.add("proximity")
                elif v <= th.vessel_distance_watch_m:
                    indicators.append(f"Simulated vessel approaching corridor ({v:.1f} m <= {th.vessel_distance_watch_m} m)")
                    indicator_groups.add("proximity")

            # Simulated DAS Vibration RMS
            elif s_id == "das_rms" and isinstance(v, (int, float)):
                if v >= th.das_rms_urgent:
                    indicators.append(f"Simulated DAS acoustic RMS critical ({v:.3f} >= {th.das_rms_urgent})")
                    indicator_groups.add("vibration")
                elif v >= th.das_rms_watch:
                    indicators.append(f"Simulated DAS acoustic RMS elevated ({v:.3f} >= {th.das_rms_watch})")
                    indicator_groups.add("vibration")

            # Simulated Cable Strain
            elif s_id == "cable_strain" and isinstance(v, (int, float)):
                if v >= th.cable_strain_urgent:
                    indicators.append(f"Simulated cable mechanical strain critical ({v:.1f} >= {th.cable_strain_urgent} ustrain)")
                    indicator_groups.add("mechanical_strain")
                elif v >= th.cable_strain_watch:
                    indicators.append(f"Simulated cable mechanical strain elevated ({v:.1f} >= {th.cable_strain_watch} ustrain)")
                    indicator_groups.add("mechanical_strain")

            # Simulated Seafloor Temperature
            elif s_id == "seafloor_temperature" and isinstance(v, (int, float)):
                # Baseline 4.0 deg C
                if abs(v - 4.0) >= th.temperature_delta_watch:
                    indicators.append(f"Simulated benthic temperature anomaly ({v:.2f} °C, delta >= {th.temperature_delta_watch} °C)")
                    indicator_groups.add("thermal")

            # Simulated Cable Condition Index
            elif s_id == "cable_health_index" and isinstance(v, (int, float)):
                if v <= th.cable_health_urgent:
                    indicators.append(f"Simulated cable condition index critical ({v:.3f} <= {th.cable_health_urgent})")
                    indicator_groups.add("integrity")
                elif v <= th.cable_health_advisory:
                    indicators.append(f"Simulated cable condition index degraded ({v:.3f} <= {th.cable_health_advisory})")
                    indicator_groups.add("integrity")

        n_indicators = len(indicators)
        n_independent_groups = len(indicator_groups)
        reasons: list[str] = []

        # 5. Temporal Persistence & Hysteresis Management
        if n_indicators > 0:
            self.anomaly_streak += 1
            self.quiet_streak = 0
        else:
            self.quiet_streak += 1
            self.anomaly_streak = 0

        # Target state calculation with hysteresis
        target_state = self.current_state
        confidence = 0.60

        if n_indicators == 0:
            # Quiet conditions
            if self.current_state == EarlyWarningState.W0:
                target_state = EarlyWarningState.W0
                confidence = 0.95
            elif self.quiet_streak >= th.deescalation_quiet_frames:
                # Sustained quiet period achieved: step down warning level
                if self.current_state == EarlyWarningState.W3:
                    target_state = EarlyWarningState.W2
                    confidence = 0.75
                    reasons.append(f"De-escalated to W2 after {self.quiet_streak} quiet frames")
                elif self.current_state == EarlyWarningState.W2:
                    target_state = EarlyWarningState.W1
                    confidence = 0.65
                    reasons.append(f"De-escalated to W1 after {self.quiet_streak} quiet frames")
                elif self.current_state in (EarlyWarningState.W1, EarlyWarningState.WX):
                    target_state = EarlyWarningState.W0
                    confidence = 0.95
                    reasons.append(f"De-escalated to W0 after {self.quiet_streak} quiet frames")
                # Reset quiet streak to 1 to require sustained quiet for next step down
                self.quiet_streak = 1
            else:
                # Hold current state during brief transient quiet / jitter
                target_state = self.current_state
                confidence = max(0.50, confidence)
                reasons.append(f"Holding {self.current_state.value} (quiet streak {self.quiet_streak}/{th.deescalation_quiet_frames})")

        else:
            # Active indicators present
            # Rule: W3 requires sustained streak (>= persistence_urgent_frames) AND at least 2 independent sensor groups
            if (self.anomaly_streak >= th.persistence_urgent_frames and n_independent_groups >= 2) or (
                self.current_state == EarlyWarningState.W3 and n_independent_groups >= 2
            ):
                target_state = EarlyWarningState.W3
                confidence = 0.90
                reasons.append(f"Urgent W3: {n_independent_groups} independent indicator groups active (streak: {self.anomaly_streak})")

            # Rule: W2 requires either multiple independent groups OR persistent anomaly (>= persistence_advisory_frames)
            elif (n_independent_groups >= 2) or (self.anomaly_streak >= th.persistence_advisory_frames) or (
                self.current_state == EarlyWarningState.W2
            ):
                target_state = EarlyWarningState.W2
                confidence = 0.78
                if n_independent_groups >= 2:
                    reasons.append(f"Advisory W2: {n_independent_groups} independent sensor indicator groups corroborating")
                else:
                    reasons.append(f"Advisory W2: Anomaly persistent across {self.anomaly_streak} frames")

            # Rule: W1 Watch is triggered by initial anomaly onset or approaching vessel
            else:
                target_state = EarlyWarningState.W1
                confidence = 0.65
                reasons.append(f"Watch W1: Anomaly onset ({indicators[0]})")

        # In degraded quality, cap state to WX if confidence is crippled
        if data_quality == DataQuality.DEGRADED:
            confidence = max(0.20, confidence - 0.25)
            reasons.append("Confidence penalized due to degraded channel quality")

        self.current_state = target_state

        # Human-readable explanation synthesis
        if target_state == EarlyWarningState.W0:
            explanation = "Nominal conditions: all monitored channels within normal parameters."
        elif target_state == EarlyWarningState.W1:
            explanation = f"Watch advisory: initial anomaly detected ({indicators[0] if indicators else 'unspecified'})."
        elif target_state == EarlyWarningState.W2:
            explanation = f"Advisory alert: {n_indicators} indicator(s) across {n_independent_groups} independent group(s) observed."
        elif target_state == EarlyWarningState.W3:
            explanation = f"URGENT WARNING: Sustained critical disturbance verified across {n_independent_groups} independent channel groups."
        else:
            explanation = "Data quality alert: warning engine suspended due to sensor communication / integrity issues."

        decision = EarlyWarningDecision(
            state=target_state,
            mode=mode,
            confidence=confidence,
            triggering_indicators=tuple(indicators),
            evidence_sources=evidence_sources,
            data_quality=data_quality,
            explanation=explanation,
            timestamp=now,
            scenario_id=scenario_id,
            reasons=tuple(reasons),
            active_indicators_count=n_indicators,
            metadata={
                "anomaly_streak": self.anomaly_streak,
                "quiet_streak": self.quiet_streak,
                "independent_groups": sorted(list(indicator_groups)),
            },
        )
        self._history.append(decision)
        return decision
