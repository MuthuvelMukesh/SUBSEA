"""Automated Tests for Independent Early Warning Engine and Data Provenance.

Verifies:
- Data quality validation (missing, stale, out of range, backwards drift, contradictory)
- Early warning state transitions: W0 -> W1 -> W2 -> W3
- Fail-safe WX state on degraded/stale/missing channels
- Recovery and gradual de-escalation with hysteresis
- Multi-sensor corroboration requirement (single signal cannot reach W3 alone)
- Physical-Only mode isolation from simulated inputs
- Hybrid demonstration mode provenance tracking and explanation
- Strict decoupling from existing T0/T1/T2/T3/TX disturbance classification
"""

from __future__ import annotations

import pytest

from subsea.decision import decide
from subsea.early_warning import (
    EarlyWarningDecision,
    EarlyWarningEngine,
    EarlyWarningState,
    EarlyWarningThresholds,
)
from subsea.models import DecisionState
from subsea.provenance_quality import (
    CHANNEL_BOUNDS,
    DataQuality,
    DataSource,
    DataQualityValidator,
    OperatingMode,
    SensorReading,
)


# -----------------------------------------------------------------------------
# Data Quality & Provenance Validation Tests
# -----------------------------------------------------------------------------

def test_data_quality_validator_missing_value():
    validator = DataQualityValidator()
    r = SensorReading(
        sensor_id="vessel_distance",
        source=DataSource.SIMULATED,
        timestamp=100.0,
        value=None,
        unit="m",
    )
    validated = validator.validate_reading(r, now=100.0)
    assert validated.quality == DataQuality.MISSING
    assert not validated.is_usable
    assert "Value is null or unavailable" in validated.metadata["quality_reasons"]


def test_data_quality_validator_out_of_range():
    validator = DataQualityValidator()
    # ultrasonic distance bound is [0.02, 5.0] m
    r = SensorReading(
        sensor_id="ultrasonic_distance",
        source=DataSource.PHYSICAL,
        timestamp=100.0,
        value=25.0, # 25 meters exceeds benchtop limit
        unit="m",
    )
    validated = validator.validate_reading(r, now=100.0)
    assert validated.quality == DataQuality.OUT_OF_RANGE
    assert not validated.is_usable


def test_data_quality_validator_stale_detection():
    validator = DataQualityValidator(stale_threshold_s=2.0)
    r = SensorReading(
        sensor_id="das_rms",
        source=DataSource.SIMULATED,
        timestamp=100.0,
        value=0.5,
        unit="units",
    )
    # Check with current time 5 seconds later
    validated = validator.validate_reading(r, now=105.0)
    assert validated.quality == DataQuality.STALE
    assert not validated.is_usable


def test_data_quality_validator_backwards_timestamp():
    validator = DataQualityValidator()
    r1 = SensorReading("piezo_vibration", DataSource.PHYSICAL, timestamp=10.0, value=0, unit="flag")
    validator.validate_reading(r1)

    r2 = SensorReading("piezo_vibration", DataSource.PHYSICAL, timestamp=9.5, value=0, unit="flag")
    validated = validator.validate_reading(r2)
    assert validated.quality == DataQuality.INVALID
    assert "Timestamp decreased" in validated.metadata["quality_reasons"][0]


# -----------------------------------------------------------------------------
# Early Warning Engine State Machine Tests
# -----------------------------------------------------------------------------

def test_early_warning_normal_baseline():
    """Nominal readings must stay at W0 with high confidence."""
    engine = EarlyWarningEngine()
    readings = {
        "vessel_distance": SensorReading("vessel_distance", DataSource.SIMULATED, 100.0, 150.0, "m"),
        "das_rms": SensorReading("das_rms", DataSource.SIMULATED, 100.0, 0.08, "units"),
        "cable_strain": SensorReading("cable_strain", DataSource.SIMULATED, 100.0, 5.0, "microstrain"),
        "seafloor_temperature": SensorReading("seafloor_temperature", DataSource.SIMULATED, 100.0, 4.0, "deg_c"),
    }
    dec = engine.evaluate(readings, mode=OperatingMode.HYBRID_DEMO, timestamp=100.0)
    assert dec.state == EarlyWarningState.W0
    assert dec.confidence >= 0.90
    assert dec.active_indicators_count == 0


def test_early_warning_single_anomaly_watch_w1():
    """Initial single anomaly (e.g. vessel entering 60m corridor) triggers W1 Watch."""
    engine = EarlyWarningEngine()
    readings = {
        "vessel_distance": SensorReading("vessel_distance", DataSource.SIMULATED, 100.0, 55.0, "m"), # < 60m threshold
        "das_rms": SensorReading("das_rms", DataSource.SIMULATED, 100.0, 0.08, "units"),
        "cable_strain": SensorReading("cable_strain", DataSource.SIMULATED, 100.0, 5.0, "microstrain"),
    }
    dec = engine.evaluate(readings, mode=OperatingMode.HYBRID_DEMO, timestamp=100.0)
    assert dec.state == EarlyWarningState.W1
    assert dec.confidence >= 0.60
    assert dec.active_indicators_count == 1
    assert "proximity" in dec.metadata["independent_groups"]


def test_early_warning_persistence_escalation_w1_to_w2():
    """A single persistent anomaly must escalate from W1 to W2 Advisory after threshold frames."""
    engine = EarlyWarningEngine()
    readings = {
        "das_rms": SensorReading("das_rms", DataSource.SIMULATED, 100.0, 0.35, "units"), # Elevated vibration
    }
    # Step 1: W1 onset
    d1 = engine.evaluate(readings, timestamp=100.0)
    assert d1.state == EarlyWarningState.W1

    # Step 2: Still W1
    d2 = engine.evaluate(readings, timestamp=100.3)
    assert d2.state == EarlyWarningState.W1

    # Step 3: Persistence reached -> W2 Advisory
    d3 = engine.evaluate(readings, timestamp=100.6)
    assert d3.state == EarlyWarningState.W2
    assert "Advisory W2: Anomaly persistent" in d3.reasons[0]


def test_multi_sensor_corroboration_w3_urgent():
    """Sustained critical disturbance across 2+ independent groups escalates to W3 Urgent."""
    engine = EarlyWarningEngine()

    # Evaluate multiple consecutive frames to fulfill persistence_urgent_frames (5 frames)
    dec = None
    for i in range(6):
        t = 100.0 + (i * 0.3)
        readings = {
            "vessel_distance": SensorReading("vessel_distance", DataSource.SIMULATED, t, 8.0, "m"),
            "das_rms": SensorReading("das_rms", DataSource.SIMULATED, t, 2.2, "units"),
            "cable_strain": SensorReading("cable_strain", DataSource.SIMULATED, t, 320.0, "microstrain"),
        }
        dec = engine.evaluate(readings, timestamp=t)

    assert dec is not None
    assert dec.state == EarlyWarningState.W3
    assert dec.confidence >= 0.85
    assert len(dec.metadata["independent_groups"]) >= 2


def test_single_signal_cannot_reach_w3_alone():
    """Architectural constraint: a single isolated signal group CANNOT escalate to W3 Urgent."""
    engine = EarlyWarningEngine()

    # Run for 15 frames: must cap at W2 Advisory, NEVER reach W3 Urgent
    dec = None
    for i in range(15):
        t = 100.0 + (i * 0.3)
        readings = {
            "vessel_distance": SensorReading("vessel_distance", DataSource.SIMULATED, t, 5.0, "m"),
            "das_rms": SensorReading("das_rms", DataSource.SIMULATED, t, 0.08, "units"), # quiet
            "cable_strain": SensorReading("cable_strain", DataSource.SIMULATED, t, 5.0, "microstrain"), # quiet
        }
        dec = engine.evaluate(readings, timestamp=t)

    assert dec is not None
    assert dec.state == EarlyWarningState.W2
    assert dec.state != EarlyWarningState.W3


def test_fail_safe_wx_on_stale_or_missing_channels():
    """Missing or stale channels must transition the warning engine to fail-safe WX."""
    engine = EarlyWarningEngine()
    readings = {
        "das_rms": SensorReading("das_rms", DataSource.SIMULATED, 100.0, 1.5, "units", quality=DataQuality.STALE),
    }
    dec = engine.evaluate(readings, timestamp=100.0)
    assert dec.state == EarlyWarningState.WX
    assert dec.confidence == 0.0
    assert dec.data_quality == DataQuality.STALE
    assert "Early warning suspended" in dec.explanation


def test_warning_recovery_and_deescalation():
    """After disturbance cessation, engine gradually steps down (W3 -> W2 -> W1 -> W0) with hysteresis."""
    engine = EarlyWarningEngine()

    # Reach W3
    t = 100.0
    for i in range(6):
        t = 100.0 + (i * 0.3)
        severe_readings = {
            "vessel_distance": SensorReading("vessel_distance", DataSource.SIMULATED, t, 5.0, "m"),
            "das_rms": SensorReading("das_rms", DataSource.SIMULATED, t, 2.0, "units"),
        }
        engine.evaluate(severe_readings, timestamp=t)
    assert engine.current_state == EarlyWarningState.W3

    # Now transition to quiet normal readings
    states = []
    # 25 quiet steps (7.5s)
    for i in range(25):
        t += 0.3
        quiet_readings = {
            "vessel_distance": SensorReading("vessel_distance", DataSource.SIMULATED, t, 200.0, "m"),
            "das_rms": SensorReading("das_rms", DataSource.SIMULATED, t, 0.08, "units"),
        }
        d = engine.evaluate(quiet_readings, timestamp=t)
        states.append(d.state)

    # Must observe stepped de-escalation
    assert EarlyWarningState.W2 in states
    assert EarlyWarningState.W1 in states
    assert states[-1] == EarlyWarningState.W0


# -----------------------------------------------------------------------------
# Operating Mode & Provenance Isolation Tests
# -----------------------------------------------------------------------------

def test_physical_only_mode_strictly_rejects_simulated_inputs():
    """In PHYSICAL_ONLY mode, simulated channels must be completely ignored and excluded."""
    engine = EarlyWarningEngine()
    mixed_readings = {
        "piezo_vibration": SensorReading("piezo_vibration", DataSource.PHYSICAL, 100.0, 1, "flag"),
        "das_rms": SensorReading("das_rms", DataSource.SIMULATED, 100.0, 5.0, "units"), # simulated
        "vessel_distance": SensorReading("vessel_distance", DataSource.SIMULATED, 100.0, 2.0, "m"), # simulated
    }

    dec = engine.evaluate(mixed_readings, mode=OperatingMode.PHYSICAL_ONLY, timestamp=100.0)
    assert dec.mode == OperatingMode.PHYSICAL_ONLY
    # Only physical channels are included in evidence
    assert set(dec.evidence_sources.keys()) == {"piezo_vibration"}
    assert dec.evidence_sources["piezo_vibration"] == "PHYSICAL"
    assert "das_rms" not in dec.evidence_sources
    assert "vessel_distance" not in dec.evidence_sources


def test_physical_only_mode_disconnected_hardware_returns_wx():
    """In PHYSICAL_ONLY mode when hardware is disconnected (no physical readings), state must be WX."""
    engine = EarlyWarningEngine()
    sim_only_readings = {
        "das_rms": SensorReading("das_rms", DataSource.SIMULATED, 100.0, 0.08, "units"),
    }
    dec = engine.evaluate(sim_only_readings, mode=OperatingMode.PHYSICAL_ONLY, timestamp=100.0)
    assert dec.state == EarlyWarningState.WX
    assert dec.confidence == 0.0
    assert "Physical hardware disconnected" in dec.reasons[0]


def test_t0_tx_classification_independence():
    """Existing T0-TX decision logic and W0-WX early warning engine operate independently."""
    # Subsea decision logic
    t_decision = decide(
        physical_confidence=0.15,
        association_confidence=0.10,
        reliability=0.95,
        uncertainty=0.08,
    )
    assert t_decision == DecisionState.T0

    # Early warning engine evaluating advance vessel approach (W1)
    engine = EarlyWarningEngine()
    readings = {
        "vessel_distance": SensorReading("vessel_distance", DataSource.SIMULATED, 100.0, 50.0, "m"),
    }
    w_decision = engine.evaluate(readings, timestamp=100.0)
    assert w_decision.state == EarlyWarningState.W1

    # T decision remains T0 (nominal unperturbed cable), while W decision is W1 (advance watch)
    assert t_decision.value == "T0"
    assert w_decision.state.value == "W1"
