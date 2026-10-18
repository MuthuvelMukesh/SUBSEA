#!/usr/bin/env python3
"""CLI entry point for Hardware-in-the-Loop (HIL) AbyssLink Bridge.

Connects to live ESP32 serial port, deterministic mock emulator, or replay log,
synthesizes 50 Hz accelerometer observations, and runs the Subsea research pipeline.

Scientific Integrity Notice:
Data processed by this bridge is tagged with data_kind="HIL_SIMULATED_ACCEL".
Accelerometer data is synthesized and does not represent subsea acoustic physics.
"""

from __future__ import annotations

import argparse
import datetime
import json
from pathlib import Path
import sys

# Ensure Subsea src is on Python search path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from subsea.decision import decide
from subsea.hil_abysslink import (
    HILBridge,
    HILConfig,
    MockAbyssLinkSource,
    ReplayAbyssLinkSource,
    SerialAbyssLinkSource,
    write_pointer,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run AbyssLink Hardware-in-the-Loop (HIL) Bridge with Subsea pipeline.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--mock", action="store_true", help="Run with deterministic mock source")
    group.add_argument("--port", type=str, help="Serial COM port (e.g. COM3 or /dev/ttyUSB0)")
    group.add_argument("--replay", type=str, help="Path to JSONL recording file to replay")

    parser.add_argument("--scenario", type=str, default="approach_vibration",
                        help="Scenario for mock mode (approach_vibration, far_quiet, vibration_no_vessel, link_broken_transmitting, ldr_high_transmission_off, telemetry_gap, no_echo)")
    parser.add_argument("--baud", type=int, default=115200, help="Serial baud rate")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for deterministic synthesis")
    parser.add_argument("--config", type=str, default=None, help="Path to YAML config file")
    parser.add_argument("--schedule", type=str, default=None, help="Path to injection schedule JSON")
    parser.add_argument("--send-commands", action="store_true",
                        help="Send START/STOP_TRANSMISSION commands to serial port (PASSIVE by default)")
    parser.add_argument("--replay-baselines", action="store_true",
                        help="Evaluate decisions against baseline decision methods")
    parser.add_argument("--max-packets", type=int, default=None,
                        help="Maximum packets to process (defaults to 100 in mock mode)")
    parser.add_argument("--output-dir", type=str, default=None,
                        help="Custom output directory (defaults to artifacts/hil/run-<UTC>)")

    args = parser.parse_args()
    root_dir = Path(__file__).resolve().parent.parent

    # Default to mock mode if no source specified
    if not args.mock and not args.port and not args.replay:
        args.mock = True

    # Load configuration
    cfg_path = Path(args.config) if args.config else (root_dir / "config" / "hil_abysslink.yaml")
    if cfg_path.is_file():
        config = HILConfig.from_yaml(cfg_path)
    else:
        config = HILConfig()

    # Determine output directory
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        utc_ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output_dir = root_dir / "artifacts" / "hil" / f"run-{utc_ts}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Initialize data source
    serial_source: SerialAbyssLinkSource | None = None
    if args.mock:
        total_pkts = args.max_packets if args.max_packets is not None else 100
        source = MockAbyssLinkSource(
            seed=args.seed,
            scenario=args.scenario,
            config=config,
            total_packets=total_pkts,
        )
    elif args.replay:
        source = ReplayAbyssLinkSource(path=args.replay, seed=args.seed)
    elif args.port:
        serial_source = SerialAbyssLinkSource(port=args.port, baudrate=args.baud)
        source = serial_source
        if args.send_commands:
            print(f"[HIL Bridge] Sending START_TRANSMISSION to {args.port}...")
            serial_source.send_command("START_TRANSMISSION")
        else:
            print("[HIL Bridge] Running in PASSIVE mode (no serial commands sent)")
    else:
        raise ValueError("Invalid source configuration")

    # Run bridge
    print(f"[HIL Bridge] Initializing run in {output_dir}")
    print(f"[HIL Bridge] Data Kind: HIL_SIMULATED_ACCEL | Seed: {args.seed}")
    bridge = HILBridge(
        source=source,
        output_dir=output_dir,
        config=config,
        schedule_path=args.schedule,
        seed=args.seed,
    )

    try:
        manifest = bridge.run(max_packets=args.max_packets)
    finally:
        if serial_source is not None:
            if args.send_commands:
                print(f"[HIL Bridge] Sending STOP_TRANSMISSION to {args.port}...")
                serial_source.send_command("STOP_TRANSMISSION")
            serial_source.close()

    # Read decisions log for summary analytics
    decisions_path = output_dir / "decisions.jsonl"
    decisions: list[dict] = []
    if decisions_path.is_file():
        decisions = [
            json.loads(line)
            for line in decisions_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    # Compute time to first escalation (first non-T0 decision)
    first_escalation: dict | None = None
    for d in decisions:
        if d.get("decision") != "T0":
            first_escalation = d
            break

    # Replay baselines if requested
    baseline_counts: dict[str, dict[str, int]] = {}
    if args.replay_baselines and decisions:
        methods = ["physical_only", "weighted", "without_uncertainty", "without_health"]
        for m in methods:
            baseline_counts[m] = {"T0": 0, "T1": 0, "T2": 0, "T3": 0, "TX": 0}

        for d in decisions:
            pc = d["physical_confidence"]
            ac = d["association_confidence"]
            rel = d["reliability"]
            unc = d["uncertainty"]

            d_phys = decide(physical_confidence=pc, association_confidence=0.0, reliability=1.0, uncertainty=0.0).value
            d_weight = decide(physical_confidence=pc, association_confidence=ac, reliability=1.0, uncertainty=0.0).value
            d_no_unc = decide(physical_confidence=pc, association_confidence=ac, reliability=rel, uncertainty=0.0).value
            d_no_hlth = decide(physical_confidence=pc, association_confidence=ac, reliability=1.0, uncertainty=unc).value

            baseline_counts["physical_only"][d_phys] += 1
            baseline_counts["weighted"][d_weight] += 1
            baseline_counts["without_uncertainty"][d_no_unc] += 1
            baseline_counts["without_health"][d_no_hlth] += 1

    # Print Summary Table
    print("\n" + "=" * 72)
    print("           ABYSSLINK HARDWARE-IN-THE-LOOP (HIL) EXECUTION SUMMARY")
    print("=" * 72)
    print(f"Run ID:                 {manifest.get('run_id')}")
    print(f"Data Kind:              {manifest.get('data_kind')}")
    print(f"Seed:                   {manifest.get('seed')}")
    print(f"Total Packets:          {manifest.get('packet_count')}")
    print(f"Malformed Lines:        {manifest.get('malformed_count')}")
    print(f"Execution Duration:     {manifest.get('duration_s', 0.0):.2f} s")
    print("-" * 72)
    print("Proposed Pipeline Decisions:")
    counts = manifest.get("decision_counts", {})
    for dec_label in ["T0", "T1", "T2", "T3", "TX"]:
        pct = (counts.get(dec_label, 0) / max(1, manifest.get('packet_count', 1))) * 100
        desc = {
            "T0": "Safe background / quiet",
            "T1": "Uncorroborated physical disturbance",
            "T2": "Corroborated interaction alert",
            "T3": "High-confidence imminent risk",
            "TX": "Fail-closed / degraded sensor alert",
        }.get(dec_label, "")
        print(f"  {dec_label:2s} ({desc:36s}): {counts.get(dec_label, 0):4d} ({pct:5.1f}%)")

    print("-" * 72)
    if first_escalation:
        print(f"First Escalation:       Packet #{first_escalation.get('sequence')} at t={first_escalation.get('timestamp'):.2f}s -> {first_escalation.get('decision')}")
        print(f"                        (Physical: {first_escalation.get('physical_confidence'):.2f}, Association: {first_escalation.get('association_confidence'):.2f}, Uncertainty: {first_escalation.get('uncertainty'):.2f})")
    else:
        print("First Escalation:       None (all decisions remained T0)")

    if args.replay_baselines and baseline_counts:
        print("-" * 72)
        print("Baseline Comparison Decision Distributions:")
        for m, mcounts in baseline_counts.items():
            print(f"  {m:20s}: T0={mcounts['T0']:3d} | T1={mcounts['T1']:3d} | T2={mcounts['T2']:3d} | T3={mcounts['T3']:3d} | TX={mcounts['TX']:3d}")

    print("-" * 72)
    print(f"Manifest Path:          {output_dir / 'manifest.json'}")
    print(f"Decisions Log:          {output_dir / 'decisions.jsonl'}")
    print(f"Raw Log:                {output_dir / 'raw.jsonl'}")
    print(f"Web Pointer:            {root_dir / 'web' / 'hil' / 'latest.json'}")
    print("=" * 72 + "\n")


if __name__ == "__main__":
    main()
