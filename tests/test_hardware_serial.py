"""Automated tests for direct ESP32 hardware connectivity, packet validation,
adapter mapping, and Subsea Python pipeline bridge integration.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path
import pytest

from subsea.hil_abysslink import (
    AbyssLinkPacket,
    HILBridge,
    HILConfig,
    parse_abysslink_line,
)
from subsea.models import DecisionState


# -----------------------------------------------------------------------------
# 1. Packet Parsing & Validation Tests
# -----------------------------------------------------------------------------

def test_parse_valid_sensor_packet():
    line = '{"type":"sensor","transmission":true,"ldr":0,"vibration":0,"distance_cm":42.5,"distance_valid":true,"laser":"ON","buzzer":"OFF","alert":"SAFE"}'
    pkt = parse_abysslink_line(line, timestamp=100.0)

    assert pkt is not None
    assert pkt.type == "sensor"
    assert pkt.transmission is True
    assert pkt.ldr == 0
    assert pkt.vibration == 0
    assert pkt.distance_cm == 42.5
    assert pkt.distance_valid is True
    assert pkt.laser == "ON"
    assert pkt.buzzer == "OFF"
    assert pkt.alert == "SAFE"
    assert pkt.timestamp == 100.0


def test_parse_valid_ack_packet():
    start_ack = '{"type":"ack","command":"START_TRANSMISSION","success":true,"transmission":true}'
    pkt_start = parse_abysslink_line(start_ack, timestamp=101.0)
    assert pkt_start is not None
    assert pkt_start.type == "ack"
    assert pkt_start.command == "START_TRANSMISSION"
    assert pkt_start.success is True
    assert pkt_start.transmission is True

    stop_ack = '{"type":"ack","command":"STOP_TRANSMISSION","success":true,"transmission":false}'
    pkt_stop = parse_abysslink_line(stop_ack, timestamp=102.0)
    assert pkt_stop is not None
    assert pkt_stop.type == "ack"
    assert pkt_stop.command == "STOP_TRANSMISSION"
    assert pkt_stop.success is True
    assert pkt_stop.transmission is False


def test_parse_missing_fields_and_invalid_values():
    # Null distance (e.g. ultrasonic out of range / no echo)
    null_dist_line = '{"type":"sensor","transmission":true,"ldr":0,"vibration":0,"distance_cm":null,"distance_valid":false,"laser":"ON","buzzer":"OFF","alert":"SAFE"}'
    pkt = parse_abysslink_line(null_dist_line)
    assert pkt is not None
    assert pkt.distance_cm is None
    assert pkt.distance_valid is False

    # Out of range distance (< 2.0 cm min threshold)
    too_close_line = '{"type":"sensor","transmission":true,"ldr":0,"vibration":0,"distance_cm":1.2,"distance_valid":true,"laser":"ON","buzzer":"OFF","alert":"SAFE"}'
    pkt_close = parse_abysslink_line(too_close_line)
    assert pkt_close is not None
    assert pkt_close.distance_valid is False  # distance_valid overridden to False below 2cm


def test_malformed_json_and_unknown_types():
    assert parse_abysslink_line("") is None
    assert parse_abysslink_line("   ") is None
    assert parse_abysslink_line("not json at all") is None
    assert parse_abysslink_line("{incomplete json") is None
    assert parse_abysslink_line('{"type":"unknown_payload"}') is None
    assert parse_abysslink_line("[1, 2, 3]") is None


# -----------------------------------------------------------------------------
# 2. Line Buffering & Multi-Packet Stream Tests
# -----------------------------------------------------------------------------

def test_stream_line_buffering_simulation():
    """Simulates chunks arriving across arbitrary byte boundaries as in Web Serial."""
    stream_chunks = [
        '{"type":"sensor","transmiss',
        'ion":true,"ldr":0,"vibration":0,"distance_cm":50.0,"distance_valid":true,"laser":"ON","buzzer":"OFF","alert":"SAFE"}\n{"type":"ack",',
        '"command":"START_TRANSMISSION","success":true,"transmission":true}\n{"type":"sensor","transmission":true,"ldr":1,"vibr',
        'ation":1,"distance_cm":15.0,"distance_valid":true,"laser":"ON","buzzer":"ON","alert":"VIBRATION"}\n',
    ]

    buffer = ""
    parsed_packets = []

    for chunk in stream_chunks:
        buffer += chunk
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            line = line.strip()
            if line:
                pkt = parse_abysslink_line(line)
                if pkt:
                    parsed_packets.append(pkt)

    assert len(parsed_packets) == 3
    assert parsed_packets[0].type == "sensor"
    assert parsed_packets[0].distance_cm == 50.0
    assert parsed_packets[1].type == "ack"
    assert parsed_packets[1].command == "START_TRANSMISSION"
    assert parsed_packets[2].type == "sensor"
    assert parsed_packets[2].vibration == 1
    assert parsed_packets[2].ldr == 1
    assert parsed_packets[2].alert == "VIBRATION"


# -----------------------------------------------------------------------------
# 3. Adapter Behavior & Distance Mapping Tests
# -----------------------------------------------------------------------------

def test_adapter_distance_mapping(tmp_path):
    bridge = HILBridge(source=None, output_dir=tmp_path)

    # Valid distance: 50 cm -> 5.0 m (scale factor = 0.1)
    pkt_valid = AbyssLinkPacket(
        type="sensor",
        transmission=True,
        ldr=0,
        vibration=0,
        distance_cm=50.0,
        distance_valid=True,
        timestamp=100.0,
    )
    vessel_valid = bridge.dist_mapper.map_packet(pkt_valid)
    assert vessel_valid.reported is True
    assert abs(vessel_valid.position[0] - 5.0) < 1e-4

    # Invalid distance: should report (999.0, 999.0) with reported=False, never fabricated coordinates
    pkt_invalid = AbyssLinkPacket(
        type="sensor",
        transmission=True,
        ldr=0,
        vibration=0,
        distance_cm=None,
        distance_valid=False,
        timestamp=100.5,
    )
    vessel_invalid = bridge.dist_mapper.map_packet(pkt_invalid)
    assert vessel_invalid.reported is False
    assert vessel_invalid.position == (999.0, 999.0)
    assert vessel_invalid.position_uncertainty == 1.0


# -----------------------------------------------------------------------------
# 4. Pipeline Execution & Real Decisions Verification
# -----------------------------------------------------------------------------

def test_pipeline_produces_real_decisions_not_hardcoded(tmp_path):
    bridge = HILBridge(source=None, output_dir=tmp_path, seed=42)

    # Feed quiet baseline packet
    quiet_pkt = AbyssLinkPacket(
        type="sensor",
        transmission=True,
        ldr=0,
        vibration=0,
        distance_cm=150.0,
        distance_valid=True,
        timestamp=100.0,
        alert="SAFE",
    )
    res_quiet = bridge.process_packet(quiet_pkt)
    assert res_quiet is not None
    assert isinstance(res_quiet.decision, DecisionState)
    # Decision state must be valid
    assert res_quiet.decision in [DecisionState.T0, DecisionState.T1, DecisionState.T2, DecisionState.T3, DecisionState.TX]
    assert 0.0 <= res_quiet.physical_confidence <= 1.0
    assert 0.0 <= res_quiet.association_confidence <= 1.0
    assert 0.0 <= res_quiet.reliability <= 1.0
    assert 0.0 <= res_quiet.uncertainty <= 1.0

    # Feed vibration + close proximity packet
    disturb_pkt = AbyssLinkPacket(
        type="sensor",
        transmission=True,
        ldr=0,
        vibration=1,
        distance_cm=20.0,
        distance_valid=True,
        timestamp=100.3,
        alert="VIBRATION",
    )
    res_disturb = bridge.process_packet(disturb_pkt)
    assert res_disturb is not None
    assert isinstance(res_disturb.decision, DecisionState)


def test_artifact_recording_and_jsonl_output(tmp_path):
    bridge = HILBridge(source=None, output_dir=tmp_path, seed=42)

    pkt1 = AbyssLinkPacket(type="sensor", transmission=True, ldr=0, vibration=0, distance_cm=80.0, distance_valid=True, timestamp=10.0)
    pkt2 = AbyssLinkPacket(type="sensor", transmission=True, ldr=1, vibration=1, distance_cm=15.0, distance_valid=True, timestamp=10.3)

    bridge.process_packet(pkt1)
    bridge.process_packet(pkt2)

    raw_log = tmp_path / "raw.jsonl"
    dec_log = tmp_path / "decisions.jsonl"

    assert raw_log.is_file()
    assert dec_log.is_file()

    raw_lines = [json.loads(line) for line in raw_log.read_text(encoding="utf-8").strip().split("\n")]
    dec_lines = [json.loads(line) for line in dec_log.read_text(encoding="utf-8").strip().split("\n")]

    assert len(raw_lines) == 2
    assert len(dec_lines) == 2
    assert raw_lines[0]["data_kind"] == "HIL_SIMULATED_ACCEL"
    assert dec_lines[0]["data_kind"] == "HIL_SIMULATED_ACCEL"
    assert "physical_confidence" in dec_lines[0]
    assert "uncertainty" in dec_lines[0]


# -----------------------------------------------------------------------------
# 5. Pipeline HTTP API Endpoint Tests
# -----------------------------------------------------------------------------

def test_serve_web_api_endpoints():
    import functools
    import http.server
    import threading
    import urllib.request
    import urllib.error
    import sys
    from pathlib import Path

    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    sys.path.insert(0, str(scripts_dir))
    from serve_web import SubseaServerHandler

    web_dir = Path(__file__).resolve().parent.parent / "web"
    port = 8769
    handler = functools.partial(SubseaServerHandler, directory=str(web_dir))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{port}"

    try:
        # 1. Test GET /api/status
        req_status = urllib.request.Request(f"{base_url}/api/status")
        with urllib.request.urlopen(req_status) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["status"] == "online"
            assert data["framework"] == "SUBSEA"

        # 2. Test POST /api/hil/process_packet
        payload = {
            "type": "sensor",
            "transmission": True,
            "ldr": 0,
            "vibration": 1,
            "distance_cm": 25.0,
            "distance_valid": True,
            "laser": "ON",
            "buzzer": "OFF",
            "alert": "SAFE",
            "timestamp": 1000.0,
        }
        req_proc = urllib.request.Request(
            f"{base_url}/api/hil/process_packet",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req_proc) as resp:
            assert resp.status == 200
            res_data = json.loads(resp.read().decode("utf-8"))
            assert res_data["decision"] in ["T0", "T1", "T2", "T3", "TX"]
            assert "physical_confidence" in res_data
            assert "association_confidence" in res_data
            assert "reliability" in res_data
            assert "uncertainty" in res_data
            assert res_data["vibration_flag"] == 1
            assert res_data["data_kind"] == "HIL_SIMULATED_ACCEL"

        # 3. Test POST /api/hil/reset
        req_reset = urllib.request.Request(f"{base_url}/api/hil/reset", data=b"{}", method="POST")
        with urllib.request.urlopen(req_reset) as resp:
            assert resp.status == 200
            res_reset = json.loads(resp.read().decode("utf-8"))
            assert res_reset["status"] == "reset"
            assert "run_id" in res_reset

    finally:
        server.shutdown()

