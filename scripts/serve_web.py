#!/usr/bin/env python3
"""Unified Static & Pipeline Bridge HTTP Server for SUBSEA.

Serves the standalone static web front end from web/ while providing
real-time JSON endpoints for in-browser hardware Web Serial telemetry
to execute the real Subsea Python research pipeline.
"""

from __future__ import annotations

import argparse
import datetime
import functools
import hashlib
import http.server
import json
from pathlib import Path
import shutil
import sys
import time
import urllib.parse
from typing import Any

# Ensure safe console printing on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Ensure Subsea src is on Python search path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

from subsea.hil_abysslink import (
    AbyssLinkPacket,
    HILBridge,
    HILConfig,
    parse_abysslink_line,
    write_pointer,
)
from subsea.digital_twin import DigitalTwinSimulator, TwinScenario
from subsea.early_warning import EarlyWarningEngine, EarlyWarningState, EarlyWarningThresholds
from subsea.provenance_quality import DataQuality, DataSource, OperatingMode, SensorReading

# Global active HIL bridge session
CURRENT_BRIDGE: HILBridge | None = None
CURRENT_RUN_DIR: Path | None = None
CONFIG_PATH = ROOT_DIR / "config" / "hil_abysslink.yaml"

MAX_BODY_SIZE = 65536  # 64 KB
SESSION_TTL_SECONDS = 3600.0  # 1 hour


def compute_config_hash() -> str:
    """Computes a deterministic hash of early-warning thresholds and twin configuration."""
    from dataclasses import asdict
    th = EarlyWarningThresholds()
    content = json.dumps(asdict(th), sort_keys=True)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]


CONFIG_HASH = compute_config_hash()


class TwinSession:
    """Encapsulates isolated simulator, early warning state, and run history per client session."""

    def __init__(self, session_id: str, seed: int = 42, mode: OperatingMode = OperatingMode.HYBRID_DEMO) -> None:
        self.session_id = session_id
        self.seed = seed
        self.mode = mode
        self.simulator = DigitalTwinSimulator(seed=seed)
        self.early_warning = EarlyWarningEngine()
        self.last_active = time.time()
        self.history: list[dict[str, Any]] = []
        self.config_hash = CONFIG_HASH

    def touch(self) -> None:
        self.last_active = time.time()


# Session registry keyed by session_id
SESSIONS: dict[str, TwinSession] = {}


def clean_expired_sessions() -> None:
    now = time.time()
    expired = [
        sid for sid, s in SESSIONS.items()
        if sid != "default" and (now - s.last_active) > SESSION_TTL_SECONDS
    ]
    for sid in expired:
        SESSIONS.pop(sid, None)


def get_or_create_session(session_id: str | None = None) -> TwinSession:
    clean_expired_sessions()
    sid = str(session_id).strip() if session_id else "default"
    if not sid:
        sid = "default"
    if sid not in SESSIONS:
        SESSIONS[sid] = TwinSession(session_id=sid)
    session = SESSIONS[sid]
    session.touch()
    return session


# Module-level legacy aliases pointing to default session
def get_default_session() -> TwinSession:
    return get_or_create_session("default")


CURRENT_TWIN_SIM = get_default_session().simulator
CURRENT_EARLY_WARNING = get_default_session().early_warning
CURRENT_TWIN_MODE = OperatingMode.HYBRID_DEMO


def compute_indicator_groups(
    readings: dict[str, SensorReading],
    th: EarlyWarningThresholds,
) -> dict[str, Any]:
    """Computes per-group indicator status (quiet/watch/urgent), threshold comparisons, and provenance."""
    groups: dict[str, Any] = {
        "vibration": {
            "name": "Vibration & Acoustics",
            "status": "quiet",
            "value": None,
            "unit": "RMS",
            "threshold": f"watch >= {th.das_rms_watch:.2f}, urgent >= {th.das_rms_urgent:.2f}",
            "sources": [],
            "mixed_sources": False,
        },
        "proximity_physical": {
            "name": "Physical Proximity (Ultrasonic)",
            "status": "quiet",
            "value": None,
            "unit": "m",
            "threshold": f"alert <= {th.ultrasonic_distance_alert_m:.2f} m",
            "sources": [],
            "mixed_sources": False,
        },
        "proximity_vessel": {
            "name": "Vessel Proximity (AIS Corridor)",
            "status": "quiet",
            "value": None,
            "unit": "m",
            "threshold": f"watch <= {th.vessel_distance_watch_m:.1f} m, urgent <= {th.vessel_distance_urgent_m:.1f} m",
            "sources": [],
            "mixed_sources": False,
        },
        "mechanical_strain": {
            "name": "Mechanical Cable Strain",
            "status": "quiet",
            "value": None,
            "unit": "ustrain",
            "threshold": f"watch >= {th.cable_strain_watch:.1f}, urgent >= {th.cable_strain_urgent:.1f}",
            "sources": [],
            "mixed_sources": False,
        },
        "thermal": {
            "name": "Benthic Thermal",
            "status": "quiet",
            "value": None,
            "unit": "°C",
            "threshold": f"watch |delta| >= {th.temperature_delta_watch:.2f} °C",
            "sources": [],
            "mixed_sources": False,
        },
        "integrity": {
            "name": "Cable Integrity & Optical Link",
            "status": "quiet",
            "value": None,
            "unit": "index",
            "threshold": f"advisory <= {th.cable_health_advisory:.2f}, urgent <= {th.cable_health_urgent:.2f}",
            "sources": [],
            "mixed_sources": False,
        },
    }

    # 1. Vibration
    vibration_sources: set[str] = set()
    if "das_rms" in readings:
        r = readings["das_rms"]
        vibration_sources.add(r.source.value)
        groups["vibration"]["value"] = r.value
        if r.is_usable and isinstance(r.value, (int, float)):
            if r.value >= th.das_rms_urgent:
                groups["vibration"]["status"] = "urgent"
            elif r.value >= th.das_rms_watch:
                groups["vibration"]["status"] = "watch"
    if "piezo_vibration" in readings:
        r = readings["piezo_vibration"]
        vibration_sources.add(r.source.value)
        if r.is_usable and r.value == th.vibration_flag_value:
            groups["vibration"]["status"] = "urgent"
    groups["vibration"]["sources"] = sorted(list(vibration_sources))
    groups["vibration"]["mixed_sources"] = len(vibration_sources) > 1

    # 2. Physical Proximity (Ultrasonic)
    if "ultrasonic_distance" in readings:
        r = readings["ultrasonic_distance"]
        groups["proximity_physical"]["sources"] = [r.source.value]
        groups["proximity_physical"]["value"] = r.value
        if r.is_usable and isinstance(r.value, (int, float)):
            if r.value <= th.ultrasonic_distance_alert_m:
                groups["proximity_physical"]["status"] = "urgent"

    # 3. Vessel Proximity (Virtual Vessel AIS corridor)
    if "vessel_distance" in readings:
        r = readings["vessel_distance"]
        groups["proximity_vessel"]["sources"] = [r.source.value]
        groups["proximity_vessel"]["value"] = r.value
        if r.is_usable and isinstance(r.value, (int, float)):
            if r.value <= th.vessel_distance_urgent_m:
                groups["proximity_vessel"]["status"] = "urgent"
            elif r.value <= th.vessel_distance_watch_m:
                groups["proximity_vessel"]["status"] = "watch"

    # 4. Mechanical Strain
    if "cable_strain" in readings:
        r = readings["cable_strain"]
        groups["mechanical_strain"]["sources"] = [r.source.value]
        groups["mechanical_strain"]["value"] = r.value
        if r.is_usable and isinstance(r.value, (int, float)):
            if r.value >= th.cable_strain_urgent:
                groups["mechanical_strain"]["status"] = "urgent"
            elif r.value >= th.cable_strain_watch:
                groups["mechanical_strain"]["status"] = "watch"

    # 5. Thermal
    if "seafloor_temperature" in readings:
        r = readings["seafloor_temperature"]
        groups["thermal"]["sources"] = [r.source.value]
        groups["thermal"]["value"] = r.value
        if r.is_usable and isinstance(r.value, (int, float)):
            if abs(r.value - 4.0) >= th.temperature_delta_watch:
                groups["thermal"]["status"] = "watch"

    # 6. Integrity & Optical Link
    integrity_sources: set[str] = set()
    if "cable_health_index" in readings:
        r = readings["cable_health_index"]
        integrity_sources.add(r.source.value)
        groups["integrity"]["value"] = r.value
        if r.is_usable and isinstance(r.value, (int, float)):
            if r.value <= th.cable_health_urgent:
                groups["integrity"]["status"] = "urgent"
            elif r.value <= th.cable_health_advisory:
                groups["integrity"]["status"] = "watch"
    if "optical_link" in readings:
        r = readings["optical_link"]
        integrity_sources.add(r.source.value)
        if r.is_usable and (r.value == th.optical_link_fault_value or r.value in ("FAULT", "BROKEN")):
            groups["integrity"]["status"] = "urgent"
    groups["integrity"]["sources"] = sorted(list(integrity_sources))
    groups["integrity"]["mixed_sources"] = len(integrity_sources) > 1

    return groups


def compute_hold_progress(
    engine: EarlyWarningEngine,
    dt: float,
) -> dict[str, Any]:
    """Computes escalation persistence and de-escalation hold progress in seconds."""
    th = engine.thresholds
    escalation_frames = engine.anomaly_streak
    deescalation_frames = engine.quiet_streak
    escalation_s = round(escalation_frames * dt, 2)
    deescalation_s = round(deescalation_frames * dt, 2)

    target_urgent_frames = th.persistence_urgent_frames
    target_advisory_frames = th.persistence_advisory_frames
    target_quiet_frames = th.deescalation_quiet_frames

    target_escalation_frames = target_urgent_frames if engine.current_state == EarlyWarningState.W2 else target_advisory_frames
    target_escalation_s = round(target_escalation_frames * dt, 2)
    target_deescalation_s = round(target_quiet_frames * dt, 2)

    return {
        "anomaly_streak_frames": escalation_frames,
        "anomaly_streak_seconds": escalation_s,
        "quiet_streak_frames": deescalation_frames,
        "quiet_streak_seconds": deescalation_s,
        "target_escalation_frames": target_escalation_frames,
        "target_escalation_seconds": target_escalation_s,
        "target_deescalation_frames": target_quiet_frames,
        "target_deescalation_seconds": target_deescalation_s,
        "escalation_progress_ratio": round(min(1.0, escalation_frames / max(1, target_escalation_frames)), 3),
        "deescalation_progress_ratio": round(min(1.0, deescalation_frames / max(1, target_quiet_frames)), 3),
    }


def get_or_create_bridge() -> tuple[HILBridge, Path]:
    global CURRENT_BRIDGE, CURRENT_RUN_DIR
    if CURRENT_BRIDGE is None or CURRENT_RUN_DIR is None:
        utc_ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        CURRENT_RUN_DIR = ROOT_DIR / "artifacts" / "hil" / f"run-{utc_ts}"
        CURRENT_RUN_DIR.mkdir(parents=True, exist_ok=True)

        config = HILConfig.from_yaml(CONFIG_PATH) if CONFIG_PATH.is_file() else HILConfig()
        CURRENT_BRIDGE = HILBridge(source=None, output_dir=CURRENT_RUN_DIR, config=config, seed=42)
        write_pointer(CURRENT_RUN_DIR, ROOT_DIR / "web" / "hil")
        print(f"[SUBSEA Web Server] Initialized live HIL session: {CURRENT_RUN_DIR.name}")
    return CURRENT_BRIDGE, CURRENT_RUN_DIR


class SubseaServerHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        # Suppress noisy HTTP asset logs, show only API calls
        if args and str(args[0]).startswith("POST /api"):
            print(f"[API] {args[0]} - {args[1] if len(args) > 1 else ''}")

    def copyfile(self, source, outputfile) -> None:
        try:
            super().copyfile(source, outputfile)
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            pass

    def _extract_session_id(self, data: dict[str, Any] | None = None) -> str:
        """Extracts session ID from body, query param, or header, defaulting to 'default'."""
        sid = None
        if data and isinstance(data, dict):
            sid = data.get("session_id")
        if not sid:
            sid = self.headers.get("X-Session-ID") or self.headers.get("X-Session-Id")
        if not sid and "?" in self.path:
            query = self.path.split("?")[1]
            params = urllib.parse.parse_qs(query)
            sid = params.get("session", params.get("session_id", [None]))[0]
        return str(sid).strip() if sid else "default"

    def do_GET(self) -> None:
        clean_path = self.path.split("?")[0]
        if clean_path in ("/api/status", "/api/status.json"):
            sid = self._extract_session_id()
            session = get_or_create_session(sid)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            payload = {
                "status": "online",
                "framework": "SUBSEA",
                "version": "0.1.0",
                "session_id": session.session_id,
                "mode": session.mode.value,
                "pipeline": "active",
                "config_hash": session.config_hash,
                "digital_twin": {
                    "scenario": session.simulator.current_scenario.value,
                    "elapsed_s": round(session.simulator.elapsed_s, 2),
                    "phase": session.simulator.phase,
                    "early_warning_state": session.early_warning.current_state.value,
                    "supported_scenarios": [s.value for s in TwinScenario],
                    "supported_modes": [m.value for m in OperatingMode],
                    "t_event": session.simulator.ground_truth_t_event,
                },
                "data_kind": "HIL_SIMULATED_ACCEL",
            }
            self.wfile.write(json.dumps(payload).encode("utf-8"))
            return

        if clean_path == "/api/twin/export":
            sid = self._extract_session_id()
            session = get_or_create_session(sid)
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
            self.send_header("Content-Disposition", f'attachment; filename="twin_run_{session.session_id}_{int(time.time())}.jsonl"')
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            for item in session.history:
                line = json.dumps(item) + "\n"
                self.wfile.write(line.encode("utf-8"))
            return

        super().do_GET()

    def do_POST(self) -> None:
        content_len = int(self.headers.get("Content-Length", 0))
        if content_len > MAX_BODY_SIZE:
            self.send_response(413)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"Payload too large. Maximum size is {MAX_BODY_SIZE} bytes."}).encode("utf-8"))
            return

        if self.path == "/api/twin/set_scenario":
            try:
                body = self.rfile.read(content_len).decode("utf-8") if content_len else "{}"
                data = json.loads(body) if body else {}
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": f"Invalid JSON payload: {e}"}).encode("utf-8"))
                return

            scen_name = str(data.get("scenario", "normal_operation")).strip()
            valid_scenarios = [s.value for s in TwinScenario]
            if scen_name not in valid_scenarios:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "error": f"Unknown scenario '{scen_name}'. Must be one of: {valid_scenarios}"
                }).encode("utf-8"))
                return

            scen = TwinScenario(scen_name)
            seed = int(data.get("seed", 42))
            mode_str = str(data.get("mode", "HYBRID_DEMO"))
            mode = OperatingMode.PHYSICAL_ONLY if "PHYSICAL" in mode_str.upper() else OperatingMode.HYBRID_DEMO

            sid = self._extract_session_id(data)
            session = get_or_create_session(sid)
            session.seed = seed
            session.mode = mode
            session.simulator.set_scenario(scen, seed=seed)
            session.early_warning.reset()
            session.history.clear()

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            resp = {
                "status": "configured",
                "scenario": scen.value,
                "mode": session.mode.value,
                "seed": seed,
                "session_id": session.session_id,
                "config_hash": session.config_hash,
                "t_event": session.simulator.ground_truth_t_event,
            }
            self.wfile.write(json.dumps(resp).encode("utf-8"))
            return

        if self.path == "/api/twin/step":
            try:
                body = self.rfile.read(content_len).decode("utf-8") if content_len else "{}"
                data = json.loads(body) if body else {}
            except Exception:
                data = {}

            sid = self._extract_session_id(data)
            session = get_or_create_session(sid)

            # Clamp dt to a sane range [0.05, 5.0]
            try:
                raw_dt = float(data.get("dt", 0.3))
                dt = max(0.05, min(5.0, raw_dt))
            except (ValueError, TypeError):
                dt = 0.3

            frame = session.simulator.step(dt=dt)

            # In PHYSICAL_ONLY mode, simulated readings are filtered out
            readings = dict(frame.readings)
            if session.mode == OperatingMode.PHYSICAL_ONLY:
                readings = {}

            warning_dec = session.early_warning.evaluate(
                readings=readings,
                mode=session.mode,
                timestamp=frame.timestamp,
                scenario_id=session.simulator.current_scenario.value,
            )

            # Disturbance Classification heuristic benchmark (properly guarded)
            rms = frame.summary.get("vibration_rms", 0.0)
            dist = frame.summary.get("distance_m", 100.0)
            das_reading = frame.readings.get("das_rms")
            das_quality = getattr(das_reading, "quality", None) if das_reading is not None else None

            if session.mode == OperatingMode.PHYSICAL_ONLY:
                t_state = "TX"
            elif das_reading is None or das_quality in (DataQuality.INVALID, DataQuality.STALE, DataQuality.MISSING):
                t_state = "TX"
            elif rms > 1.5 and dist < 15.0:
                t_state = "T3"
            elif rms > 0.40 and dist < 40.0:
                t_state = "T2"
            elif rms > 0.40:
                t_state = "T1"
            else:
                t_state = "T0"

            indicator_groups = compute_indicator_groups(readings=readings, th=session.early_warning.thresholds)
            hold_progress = compute_hold_progress(engine=session.early_warning, dt=dt)
            step_idx = len(session.history)

            response_payload = {
                "step": step_idx,
                "timestamp": frame.timestamp,
                "elapsed_s": frame.elapsed_s,
                "phase": frame.phase,
                "mode": session.mode.value,
                "scenario": session.simulator.current_scenario.value,
                "t_event": session.simulator.ground_truth_t_event,
                "frame": frame.to_dict(),
                "early_warning": warning_dec.to_dict(),
                "twin_heuristic_state": t_state,
                "disturbance_classification": t_state,  # Backward-compatible alias
                "twin_heuristic_label": "Twin heuristic (NOT the fusion classifier)",
                "indicator_groups": indicator_groups,
                "hold_progress": hold_progress,
                "data_quality_reasons": list(warning_dec.reasons),
                "seed": session.seed,
                "config_hash": session.config_hash,
                "session_id": session.session_id,
            }

            # Save in history for JSONL export
            session.history.append({
                "step": step_idx,
                "timestamp": frame.timestamp,
                "elapsed_s": frame.elapsed_s,
                "scenario": session.simulator.current_scenario.value,
                "mode": session.mode.value,
                "phase": frame.phase,
                "early_warning": warning_dec.to_dict(),
                "twin_heuristic_state": t_state,
                "disturbance_classification": t_state,
                "frame_summary": frame.summary,
                "seed": session.seed,
                "config_hash": session.config_hash,
                "t_event": session.simulator.ground_truth_t_event,
            })

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(response_payload).encode("utf-8"))
            return

        if self.path == "/api/twin/reset":
            try:
                body = self.rfile.read(content_len).decode("utf-8") if content_len else "{}"
                data = json.loads(body) if body else {}
            except Exception:
                data = {}

            sid = self._extract_session_id(data)
            session = get_or_create_session(sid)
            session.simulator.set_scenario(TwinScenario.NORMAL_OPERATION, seed=session.seed)
            session.early_warning.reset()
            session.history.clear()

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "reset", "session_id": session.session_id}).encode("utf-8"))
            return


        if self.path == "/api/hil/reset":
            global CURRENT_BRIDGE, CURRENT_RUN_DIR
            CURRENT_BRIDGE = None
            CURRENT_RUN_DIR = None
            bridge, run_dir = get_or_create_bridge()

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            resp = {"status": "reset", "run_id": run_dir.name}
            self.wfile.write(json.dumps(resp).encode("utf-8"))
            return

        if self.path == "/api/hil/process_packet":
            try:
                content_len = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_len).decode("utf-8")
                data = json.loads(body)
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": f"Invalid JSON payload: {e}"}).encode("utf-8"))
                return

            bridge, run_dir = get_or_create_bridge()

            # Construct packet
            raw_str = json.dumps(data)
            t_now = float(data.get("timestamp", datetime.datetime.now().timestamp()))
            pkt = parse_abysslink_line(raw_str, timestamp=t_now)

            if pkt is None:
                self.send_response(422)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Failed to parse AbyssLink packet schema"}).encode("utf-8"))
                return

            # Process packet through real Subsea pipeline
            result = bridge.process_packet(pkt)

            # Sync decisions to web/hil/decisions.jsonl so static polling works concurrently
            dec_src = run_dir / "decisions.jsonl"
            web_dec = ROOT_DIR / "web" / "hil" / "decisions.jsonl"
            if dec_src.is_file():
                try:
                    shutil.copy2(dec_src, web_dec)
                except Exception:
                    pass

            if result is None:
                # E.g. ACK packet
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "acknowledged", "type": pkt.type}).encode("utf-8"))
                return

            # Evaluate early warning on physical channels
            phys_readings: dict[str, SensorReading] = {
                "piezo_vibration": SensorReading(
                    sensor_id="piezo_vibration",
                    source=DataSource.PHYSICAL,
                    timestamp=pkt.timestamp,
                    value=pkt.vibration,
                    unit="flag",
                ),
                "optical_link": SensorReading(
                    sensor_id="optical_link",
                    source=DataSource.PHYSICAL,
                    timestamp=pkt.timestamp,
                    value=pkt.ldr,
                    unit="state",
                ),
            }
            if pkt.distance_valid and pkt.distance_cm is not None:
                phys_readings["ultrasonic_distance"] = SensorReading(
                    sensor_id="ultrasonic_distance",
                    source=DataSource.PHYSICAL,
                    timestamp=pkt.timestamp,
                    value=round(pkt.distance_cm * 0.01, 3), # cm to m
                    unit="m",
                )

            warning_dec = CURRENT_EARLY_WARNING.evaluate(
                readings=phys_readings,
                mode=CURRENT_TWIN_MODE,
                timestamp=pkt.timestamp,
            )

            vessel_obs = bridge.dist_mapper.map_packet(pkt)
            response_payload = {
                "timestamp": pkt.timestamp,
                "sequence": bridge.packet_count,
                "decision": result.decision.value,
                "early_warning": warning_dec.to_dict(),
                "physical_confidence": round(result.physical_confidence, 4),
                "association_confidence": round(result.association_confidence, 4),
                "reliability": round(result.reliability, 4),
                "uncertainty": round(result.uncertainty, 4),
                "hypothesis_scores": {k: round(v, 4) for k, v in result.hypothesis_scores.items()},
                "rationale": result.rationale,
                "vessel_distance_m": round(vessel_obs.position[0], 2) if vessel_obs.reported else None,
                "vessel_speed": round(vessel_obs.speed, 2) if vessel_obs.reported else None,
                "vibration_flag": pkt.vibration,
                "ldr_flag": pkt.ldr,
                "transmission": pkt.transmission,
                "alert": pkt.alert,
                "data_kind": "HIL_SIMULATED_ACCEL",
            }

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(response_payload).encode("utf-8"))
            return

        super().do_POST()

    def do_OPTIONS(self) -> None:
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Session-ID, X-Session-Id")
        self.end_headers()



def main() -> None:
    parser = argparse.ArgumentParser(description="SUBSEA Web & Real-Time Pipeline Bridge Server")
    parser.add_argument("--port", type=int, default=8000, help="HTTP server port (default 8000)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Bind host (default 127.0.0.1)")
    args = parser.parse_args()

    web_dir = ROOT_DIR / "web"
    handler = functools.partial(SubseaServerHandler, directory=str(web_dir))
    server = http.server.ThreadingHTTPServer((args.host, args.port), handler)

    print(f"===========================================================")
    print(f">>> SUBSEA Standalone Web & Real-Time Pipeline Bridge Server <<<")
    print(f"===========================================================")
    print(f"  Local Web App URL:      http://{args.host}:{args.port}/")
    print(f"  Live Pipeline Endpoint: http://{args.host}:{args.port}/api/hil/process_packet")
    print(f"  Serving Directory:      {web_dir}")
    print(f"  Press Ctrl+C to stop.")
    print(f"===========================================================")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[SUBSEA Web Server] Shutting down cleanly...")
        server.shutdown()


if __name__ == "__main__":
    main()
