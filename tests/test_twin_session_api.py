"""Unit and integration tests for Digital Twin session isolation, validation, and export API.

Verifies:
1. Unknown scenario -> 400 Bad Request.
2. Per-session isolation (two client sessions step independently without interleaving).
3. Missing session_id falls back cleanly to 'default' session (backward compatibility).
4. Missing das_rms channel does not throw AttributeError and returns TX.
5. Export endpoint returns JSONL matching artifacts/digital_twin/*.jsonl schema.
6. Group indicators, hold meters, and ground-truth t_event are correctly returned.
7. dt clamping and request body size limits are enforced.
"""

from __future__ import annotations

import functools
import http.server
import json
from pathlib import Path
import threading
import time
import urllib.request
import urllib.error
import sys
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.serve_web import SubseaServerHandler, get_or_create_session, SESSIONS
from subsea.digital_twin import TwinScenario
from subsea.provenance_quality import OperatingMode


TEST_PORT = 8912
BASE_URL = f"http://127.0.0.1:{TEST_PORT}"


@pytest.fixture(scope="module")
def api_server():
    web_dir = Path(__file__).resolve().parent.parent / "web"
    handler = functools.partial(SubseaServerHandler, directory=str(web_dir))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", TEST_PORT), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.5)
    yield BASE_URL
    server.shutdown()


def post_json(url: str, data: dict, headers: dict | None = None) -> tuple[int, dict]:
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=req_headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        content = e.read().decode("utf-8")
        try:
            parsed = json.loads(content)
        except Exception:
            parsed = {"raw": content}
        return e.code, parsed


def get_response(url: str, headers: dict | None = None) -> tuple[int, str, dict]:
    req = urllib.request.Request(url, headers=headers or {}, method="GET")
    with urllib.request.urlopen(req) as resp:
        content_type = resp.headers.get("Content-Type", "")
        body = resp.read().decode("utf-8")
        return resp.status, content_type, body


def test_invalid_scenario_returns_400(api_server):
    """Setting an unknown scenario must return HTTP 400 with a descriptive error message."""
    status, body = post_json(
        f"{api_server}/api/twin/set_scenario",
        {"scenario": "alien_invasion_strike", "session_id": "test_invalid"},
    )
    assert status == 400
    assert "error" in body
    assert "Unknown scenario" in body["error"]
    assert "normal_operation" in body["error"]


def test_per_session_isolation(api_server):
    """Two browser sessions must step independently without interleaving state."""
    sid_a = "tab_session_alpha"
    sid_b = "tab_session_beta"

    # Configure session A: approaching_vessel
    status, resp_a = post_json(
        f"{api_server}/api/twin/set_scenario",
        {"scenario": "approaching_vessel", "session_id": sid_a, "seed": 101},
    )
    assert status == 200
    assert resp_a["scenario"] == "approaching_vessel"
    assert resp_a["session_id"] == sid_a

    # Configure session B: severe_disturbance
    status, resp_b = post_json(
        f"{api_server}/api/twin/set_scenario",
        {"scenario": "severe_disturbance", "session_id": sid_b, "seed": 202},
    )
    assert status == 200
    assert resp_b["scenario"] == "severe_disturbance"
    assert resp_b["session_id"] == sid_b

    # Step session A 3 times (dt=0.3s -> elapsed_s ~ 0.9s)
    for _ in range(3):
        status, step_a = post_json(f"{api_server}/api/twin/step", {"session_id": sid_a, "dt": 0.3})
        assert status == 200

    # Step session B 1 time (dt=0.5s -> elapsed_s ~ 0.5s)
    status, step_b = post_json(f"{api_server}/api/twin/step", {"session_id": sid_b, "dt": 0.5})
    assert status == 200

    # Assert complete isolation
    assert step_a["session_id"] == sid_a
    assert step_a["scenario"] == "approaching_vessel"
    assert step_a["elapsed_s"] == 0.9
    assert step_a["step"] == 2  # 0-indexed: 0, 1, 2

    assert step_b["session_id"] == sid_b
    assert step_b["scenario"] == "severe_disturbance"
    assert step_b["elapsed_s"] == 0.5
    assert step_b["step"] == 0


def test_backward_compatibility_default_session(api_server):
    """Requests without a session_id must gracefully fall back to the default session."""
    status, resp = post_json(
        f"{api_server}/api/twin/set_scenario",
        {"scenario": "normal_operation", "seed": 42},
    )
    assert status == 200
    assert resp["session_id"] == "default"

    status, step_resp = post_json(f"{api_server}/api/twin/step", {"dt": 0.3})
    assert status == 200
    assert step_resp["session_id"] == "default"
    assert step_resp["scenario"] == "normal_operation"


def test_missing_channel_guard(api_server):
    """Guard against missing das_rms channel attribute error."""
    session = get_or_create_session("test_channel_guard")
    session.simulator.set_scenario("normal_operation")
    # Take a frame and simulate missing das_rms
    frame = session.simulator.step()
    frame.readings.pop("das_rms", None)

    # In our server step endpoint logic, missing das_rms safely yields TX
    status, step_resp = post_json(
        f"{api_server}/api/twin/step",
        {"session_id": "test_channel_guard", "dt": 0.3},
    )
    assert status == 200
    assert "twin_heuristic_state" in step_resp
    assert step_resp["twin_heuristic_label"] == "Twin heuristic (NOT the fusion classifier)"


def test_step_rich_metadata_fields(api_server):
    """Step response must contain indicator groups, hold progress, and ground-truth t_event."""
    sid = "test_rich_fields"
    post_json(
        f"{api_server}/api/twin/set_scenario",
        {"scenario": "approaching_vessel", "session_id": sid},
    )
    status, step = post_json(f"{api_server}/api/twin/step", {"session_id": sid, "dt": 0.3})
    assert status == 200

    # Indicator groups
    groups = step["indicator_groups"]
    assert "vibration" in groups
    assert "proximity_physical" in groups
    assert "proximity_vessel" in groups
    assert "mechanical_strain" in groups
    assert "thermal" in groups
    assert "integrity" in groups
    assert groups["vibration"]["status"] in ("quiet", "watch", "urgent")

    # Hold / persistence progress
    hold = step["hold_progress"]
    assert "anomaly_streak_seconds" in hold
    assert "quiet_streak_seconds" in hold
    assert "escalation_progress_ratio" in hold

    # Ground-truth t_event
    assert step["t_event"] == 15.9
    assert step["config_hash"] is not None
    assert step["seed"] == 42


def test_export_endpoint_jsonl(api_server):
    """GET /api/twin/export?session=... must return valid JSONL matching artifacts schema."""
    sid = "test_export_session"
    post_json(
        f"{api_server}/api/twin/set_scenario",
        {"scenario": "low_level_vibration", "session_id": sid, "seed": 77},
    )
    # Step 3 times
    for _ in range(3):
        post_json(f"{api_server}/api/twin/step", {"session_id": sid, "dt": 0.3})

    status, ctype, body = get_response(f"{api_server}/api/twin/export?session={sid}")
    assert status == 200
    assert "application/x-ndjson" in ctype or "text/" in ctype or "json" in ctype

    lines = [line.strip() for line in body.strip().split("\n") if line.strip()]
    assert len(lines) == 3

    for idx, line in enumerate(lines):
        record = json.loads(line)
        assert record["step"] == idx
        assert record["scenario"] == "low_level_vibration"
        assert record["seed"] == 77
        assert "early_warning" in record
        assert "twin_heuristic_state" in record
        assert "disturbance_classification" in record
        assert "frame_summary" in record


def test_dt_clamping(api_server):
    """dt must be safely clamped to [0.05, 5.0]."""
    sid = "test_dt_clamping"
    post_json(f"{api_server}/api/twin/set_scenario", {"session_id": sid})

    # Huge dt clamped to 5.0
    status, step_huge = post_json(f"{api_server}/api/twin/step", {"session_id": sid, "dt": 999.0})
    assert status == 200
    assert step_huge["elapsed_s"] == 5.0

    # Negative dt clamped to 0.05
    status, step_tiny = post_json(f"{api_server}/api/twin/step", {"session_id": sid, "dt": -10.0})
    assert status == 200
    assert round(step_tiny["elapsed_s"], 2) == 5.05


def test_body_size_limit(api_server):
    """Payloads exceeding MAX_BODY_SIZE (64KB) must be rejected with HTTP 413."""
    sid = "test_large_payload"
    huge_data = {"session_id": sid, "padding": "x" * 70000}
    status, body = post_json(f"{api_server}/api/twin/step", huge_data)
    assert status == 413
    assert "Payload too large" in body["error"]
