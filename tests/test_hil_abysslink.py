"""Deterministic test suite for Hardware-in-the-Loop (HIL) AbyssLink Bridge."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from subsea.hil_abysslink import (
    AbyssLinkPacket,
    AccelSynthesizer,
    DistanceToVessel,
    HILBridge,
    HILConfig,
    LinkHealthTracker,
    MockAbyssLinkSource,
    ScheduleInjector,
    parse_abysslink_line,
    write_pointer,
)


def test_parse_abysslink_sensor():
    """T14: Correct parsing of all sensor telemetry fields."""
    line = (
        '{"type":"sensor","transmission":true,"ldr":0,"vibration":1,'
        '"distance_cm":42.5,"distance_valid":true,"laser":"ON","buzzer":"OFF","alert":"VIBRATION"}'
    )
    pkt = parse_abysslink_line(line, timestamp=100.5)
    assert pkt is not None
    assert pkt.type == "sensor"
    assert pkt.transmission is True
    assert pkt.ldr == 0
    assert pkt.vibration == 1
    assert pkt.distance_cm == 42.5
    assert pkt.distance_valid is True
    assert pkt.laser == "ON"
    assert pkt.buzzer == "OFF"
    assert pkt.alert == "VIBRATION"
    assert pkt.timestamp == 100.5


def test_parse_abysslink_ack():
    """T15: Ack packets are parsed and identified."""
    line = '{"type":"ack","command":"START_TRANSMISSION","success":true,"transmission":true}'
    pkt = parse_abysslink_line(line)
    assert pkt is not None
    assert pkt.type == "ack"
    assert pkt.command == "START_TRANSMISSION"
    assert pkt.success is True
    assert pkt.transmission is True


def test_malformed_lines():
    """T11: Malformed and corrupted lines are gracefully skipped."""
    bad_lines = [
        "",
        "   ",
        "rst:0x1 (POWERON_RESET),boot:0x13 (SPI_FAST_FLASH_BOOT)",
        "{corrupted json without close",
        "{\"type\": \"sensor\", \"transmission\": }",
        "hello world",
        "12345",
    ]
    for bl in bad_lines:
        assert parse_abysslink_line(bl) is None


def test_distance_invalid_not_zero():
    """T10: Invalid distance never maps to 0 cm or cable origin."""
    mapper = DistanceToVessel()

    # Null distance with invalid flag
    pkt_null = AbyssLinkPacket(type="sensor", transmission=True, distance_cm=None, distance_valid=False, timestamp=1.0)
    v_null = mapper.map_packet(pkt_null)
    assert not v_null.reported
    assert v_null.position != (0.0, 0.0)

    # Sub-minimum distance (< 2.0 cm)
    pkt_short = AbyssLinkPacket(type="sensor", transmission=True, distance_cm=1.2, distance_valid=False, timestamp=2.0)
    v_short = mapper.map_packet(pkt_short)
    assert not v_short.reported
    assert v_short.position != (0.0, 0.0)


def test_accel_synthesizer_50hz():
    """T17: AccelSynthesizer produces continuous 50 Hz samples."""
    synth = AccelSynthesizer(seed=42)
    obs = synth.synthesize(0.0, 1.0, vibration=0)
    assert len(obs) == 50
    assert obs[1].timestamp - obs[0].timestamp == pytest.approx(0.02, abs=1e-5)
    for o in obs:
        assert o.source == "hil_simulated_accel"
        assert o.metadata["data_kind"] == "HIL_SIMULATED_ACCEL"


def test_distance_to_vessel_mapping():
    """T18: Distance mapping scales correctly and estimates approach speed."""
    cfg = HILConfig()
    cfg.distance.scale_factor = 0.1
    mapper = DistanceToVessel(cfg)

    p1 = AbyssLinkPacket(type="sensor", transmission=True, distance_cm=80.0, distance_valid=True, timestamp=10.0)
    v1 = mapper.map_packet(p1)
    assert v1.position[0] == pytest.approx(8.0)
    assert v1.speed == 0.0

    p2 = AbyssLinkPacket(type="sensor", transmission=True, distance_cm=50.0, distance_valid=True, timestamp=10.3)
    v2 = mapper.map_packet(p2)
    assert v2.position[0] == pytest.approx(5.0)
    # 3.0 meters over 0.3 seconds = 10.0 m/s
    assert v2.speed == pytest.approx(10.0, abs=0.1)
    assert v2.heading == 180.0  # Approaching


def test_grace_period():
    """T16: LDR faults are ignored during grace period after START_TRANSMISSION."""
    tracker = LinkHealthTracker()

    # Inactive transmission
    p_off = AbyssLinkPacket(type="sensor", transmission=False, ldr=1, timestamp=10.0)
    tracker.update(p_off)
    assert tracker.is_healthy()

    # Transmission starts -> grace period begins
    p_start = AbyssLinkPacket(type="sensor", transmission=True, ldr=1, timestamp=10.1)
    tracker.update(p_start)
    assert tracker.is_healthy(), "Should be protected by grace period"

    # Still inside 0.5s grace period
    p_grace = AbyssLinkPacket(type="sensor", transmission=True, ldr=1, timestamp=10.4)
    tracker.update(p_grace)
    assert tracker.is_healthy(), "Still inside grace period"

    # Outside grace period, consecutive faults trigger debounce
    p_fault1 = AbyssLinkPacket(type="sensor", transmission=True, ldr=1, timestamp=10.7)
    tracker.update(p_fault1)
    p_fault2 = AbyssLinkPacket(type="sensor", transmission=True, ldr=1, timestamp=11.0)
    tracker.update(p_fault2)
    assert not tracker.is_healthy(), "Debounced fault must trigger link fault"


def test_mock_far_quiet(tmp_path):
    """T1: Far and quiet scenario produces dominant T0 baseline decisions."""
    source = MockAbyssLinkSource(scenario="far_quiet", total_packets=40)
    bridge = HILBridge(source, tmp_path, seed=42)
    summary = bridge.run()

    counts = summary["decision_counts"]
    assert counts["T0"] >= 30, "T0 must dominate quiet baseline"
    assert counts["T2"] == 0
    assert counts["T3"] == 0


def test_mock_approach_vibration(tmp_path):
    """T2: Approaching vessel with vibration escalates to T2/T3."""
    source = MockAbyssLinkSource(scenario="approach_vibration", total_packets=80)
    bridge = HILBridge(source, tmp_path, seed=42)
    summary = bridge.run()

    counts = summary["decision_counts"]
    assert counts["T2"] + counts["T3"] > 0, "Must reach T2 or T3 during close contact"

    # Inspect decisions.jsonl for association confidence
    decisions = [
        json.loads(line)
        for line in (tmp_path / "decisions.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    high_assoc = [d for d in decisions if d["association_confidence"] > 0.6]
    assert len(high_assoc) > 0, "Must achieve association confidence > 0.6"


def test_vibration_no_vessel(tmp_path):
    """T3: Physical vibration without vessel corroboration yields T1, never T2/T3."""
    source = MockAbyssLinkSource(scenario="vibration_no_vessel", total_packets=40)
    bridge = HILBridge(source, tmp_path, seed=42)
    summary = bridge.run()

    counts = summary["decision_counts"]
    assert counts["T1"] > 0, "Vibration alone must produce T1 uncorroborated disturbance"
    assert counts["T2"] == 0, "Must never produce T2 without vessel corroboration"
    assert counts["T3"] == 0, "Must never produce T3 without vessel corroboration"


def test_link_broken_transmitting(tmp_path):
    """T4: Broken optical link during transmission triggers fail-closed TX alert."""
    source = MockAbyssLinkSource(scenario="link_broken_transmitting", total_packets=40)
    bridge = HILBridge(source, tmp_path, seed=42)
    summary = bridge.run()

    counts = summary["decision_counts"]
    assert counts["TX"] > 0, "Broken optical link must escalate to TX"


def test_ldr_high_transmission_off(tmp_path):
    """T5: High LDR when laser is intentionally off is not a fault."""
    source = MockAbyssLinkSource(scenario="ldr_high_transmission_off", total_packets=40)
    bridge = HILBridge(source, tmp_path, seed=42)
    summary = bridge.run()

    counts = summary["decision_counts"]
    assert counts["TX"] == 0, "LDR high while transmission inactive must not trigger TX"


def test_telemetry_gap(tmp_path):
    """T6: Telemetry time gap causes degraded reliability or stale detection."""
    source = MockAbyssLinkSource(scenario="telemetry_gap", total_packets=35)
    bridge = HILBridge(source, tmp_path, seed=42)
    bridge.run()

    decisions = [
        json.loads(line)
        for line in (tmp_path / "decisions.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    # Check packet after the 3.0s jump
    degraded = [d for d in decisions if d["reliability"] < 1.0 or d["decision"] == "TX"]
    assert len(degraded) > 0, "Time gap must degrade reliability"


def test_ais_spoof_injection(tmp_path):
    """T7: Injected AIS spatial spoofing prevents T2/T3 false promotion."""
    schedule = {
        "injections": [
            {"timestamp_s": 1009.0, "duration_s": 10.0, "type": "ais_spoof", "offset_m": 80.0}
        ]
    }
    sched_path = tmp_path / "spoof_schedule.json"
    sched_path.write_text(json.dumps(schedule), encoding="utf-8")

    source = MockAbyssLinkSource(scenario="approach_vibration", total_packets=60)
    bridge = HILBridge(source, tmp_path, schedule_path=sched_path, seed=42)
    bridge.run()

    decisions = [
        json.loads(line)
        for line in (tmp_path / "decisions.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    # During the spoof window (t >= 1009 and t <= 1019)
    spoofed_decisions = [d for d in decisions if 1009.0 <= d["timestamp"] <= 1019.0]
    for d in spoofed_decisions:
        assert d["decision"] in {"T0", "T1", "TX"}, f"Spoofed window produced {d['decision']}"


def test_ais_timestamp_injection(tmp_path):
    """T8: Injected timestamp manipulation degrades temporal association."""
    schedule = {
        "injections": [
            {"timestamp_s": 1009.0, "duration_s": 10.0, "type": "ais_timestamp", "delta_s": 50.0}
        ]
    }
    sched_path = tmp_path / "timestamp_schedule.json"
    sched_path.write_text(json.dumps(schedule), encoding="utf-8")

    source = MockAbyssLinkSource(scenario="approach_vibration", total_packets=60)
    bridge = HILBridge(source, tmp_path, schedule_path=sched_path, seed=42)
    bridge.run()

    decisions = [
        json.loads(line)
        for line in (tmp_path / "decisions.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    injected_decisions = [d for d in decisions if 1009.0 <= d["timestamp"] <= 1019.0]
    for d in injected_decisions:
        assert d["decision"] in {"T0", "T1", "TX"}, f"Timestamp offset produced {d['decision']}"


def test_ais_suppress_injection(tmp_path):
    """T9: Injected transponder suppression forces uncorroborated state."""
    schedule = {
        "injections": [
            {"timestamp_s": 1009.0, "duration_s": 10.0, "type": "ais_suppress"}
        ]
    }
    sched_path = tmp_path / "suppress_schedule.json"
    sched_path.write_text(json.dumps(schedule), encoding="utf-8")

    source = MockAbyssLinkSource(scenario="approach_vibration", total_packets=60)
    bridge = HILBridge(source, tmp_path, schedule_path=sched_path, seed=42)
    bridge.run()

    decisions = [
        json.loads(line)
        for line in (tmp_path / "decisions.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    injected_decisions = [d for d in decisions if 1009.0 <= d["timestamp"] <= 1019.0]
    for d in injected_decisions:
        assert d["decision"] in {"T0", "T1", "TX"}, f"Suppressed transponder produced {d['decision']}"


def test_deterministic_same_seed(tmp_path):
    """T12: Identical seed produces byte-identical decisions output."""
    dir1 = tmp_path / "run1"
    dir2 = tmp_path / "run2"

    source1 = MockAbyssLinkSource(seed=42, scenario="approach_vibration", total_packets=50)
    b1 = HILBridge(source1, dir1, seed=42)
    b1.run()

    source2 = MockAbyssLinkSource(seed=42, scenario="approach_vibration", total_packets=50)
    b2 = HILBridge(source2, dir2, seed=42)
    b2.run()

    dec1 = (dir1 / "decisions.jsonl").read_bytes()
    dec2 = (dir2 / "decisions.jsonl").read_bytes()
    assert dec1 == dec2, "Decisions output must be byte-identical for identical seed"


def test_pointer_file_valid(tmp_path):
    """T13: latest.json pointer references valid existing run artifacts."""
    run_dir = tmp_path / "run_test"
    web_dir = tmp_path / "web" / "hil"
    source = MockAbyssLinkSource(scenario="far_quiet", total_packets=10)
    b = HILBridge(source, run_dir, seed=42)
    b.run()

    ptr_file = write_pointer(run_dir, web_dir=web_dir)
    assert ptr_file.is_file()

    ptr_data = json.loads(ptr_file.read_text(encoding="utf-8"))
    assert Path(ptr_data["decisions_path"]).is_file()
    assert Path(ptr_data["manifest_path"]).is_file()
    assert Path(ptr_data["raw_path"]).is_file()
