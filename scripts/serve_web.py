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
import http.server
import json
from pathlib import Path
import shutil
import sys

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

# Global active HIL bridge session
CURRENT_BRIDGE: HILBridge | None = None
CURRENT_RUN_DIR: Path | None = None
CONFIG_PATH = ROOT_DIR / "config" / "hil_abysslink.yaml"


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

    def do_GET(self) -> None:
        clean_path = self.path.split("?")[0]
        if clean_path in ("/api/status", "/api/status.json"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            payload = {
                "status": "online",
                "framework": "SUBSEA",
                "version": "0.1.0",
                "mode": "live_pipeline",
                "pipeline": "active",
                "data_kind": "HIL_SIMULATED_ACCEL",
            }
            self.wfile.write(json.dumps(payload).encode("utf-8"))
            return

        super().do_GET()

    def do_POST(self) -> None:
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

            vessel_obs = bridge.dist_mapper.map_packet(pkt)
            response_payload = {
                "timestamp": pkt.timestamp,
                "sequence": bridge.packet_count,
                "decision": result.decision.value,
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
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
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
    print(f"🌊 SUBSEA Standalone Web & Real-Time Pipeline Bridge Server")
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
