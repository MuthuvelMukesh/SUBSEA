#!/usr/bin/env python3
"""AbyssLink Digital Twin + Early Warning Multi-Sensor Demonstrator.

Runs a complete, reproducible demonstration of the Subsea Cable Digital Twin
and Multi-Sensor Early Warning Engine without requiring physical hardware.

Key Features:
- Supports all 7 Digital Twin Scenarios (Normal, Approaching Vessel, Low Vibration,
  Increasing Disturbance, Severe Disturbance, Sensor Degradation, Recovery).
- Dual Operating Modes:
  * PHYSICAL_ONLY: Uses only validated physical channels; simulated data strictly isolated.
  * HYBRID_DEMO: Synthesizes virtual DAS acoustics, kinematics, strain, and benthic temperature.
- Independent outputs:
  * T0/T1/T2/T3/TX Pipeline Disturbance Classification
  * W0/W1/W2/W3/WX Multi-Sensor Early Warning Situational Awareness
- Explicit data provenance tracking on every reading.
- Writes detailed JSONL run logs to artifacts/digital_twin/.
"""

from __future__ import annotations

import argparse
import datetime
import json
from pathlib import Path
import sys
import time
from typing import Any

# Ensure subsea src is in path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

from subsea.digital_twin import DigitalTwinFrame, DigitalTwinSimulator, TwinScenario
from subsea.early_warning import (
    EarlyWarningDecision,
    EarlyWarningEngine,
    EarlyWarningState,
    EarlyWarningThresholds,
)
from subsea.models import DecisionState
from subsea.provenance_quality import DataQuality, DataSource, OperatingMode, SensorReading


# ANSI color codes for readable terminal telemetry
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_DIM = "\033[2m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_RED = "\033[31m"
COLOR_CYAN = "\033[36m"
COLOR_MAGENTA = "\033[35m"
COLOR_BG_RED = "\033[41m\033[37m\033[1m"
COLOR_BG_YELLOW = "\033[43m\033[30m\033[1m"


# Ensure safe console printing on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def format_warning_badge(state: EarlyWarningState) -> str:
    if state == EarlyWarningState.W0:
        return f"{COLOR_GREEN}[W0: NORMAL]{COLOR_RESET}"
    if state == EarlyWarningState.W1:
        return f"{COLOR_CYAN}[W1: WATCH]{COLOR_RESET}"
    if state == EarlyWarningState.W2:
        return f"{COLOR_BG_YELLOW}[W2: ADVISORY]{COLOR_RESET}"
    if state == EarlyWarningState.W3:
        return f"{COLOR_BG_RED}[W3: URGENT WARNING]{COLOR_RESET}"
    return f"{COLOR_MAGENTA}[WX: UNKNOWN / DEGRADED]{COLOR_RESET}"


def format_decision_badge(decision: str) -> str:
    if decision == "T0":
        return f"{COLOR_GREEN}T0 (Nominal){COLOR_RESET}"
    if decision == "T1":
        return f"{COLOR_CYAN}T1 (Acoustic Unassoc){COLOR_RESET}"
    if decision == "T2":
        return f"{COLOR_YELLOW}T2 (Corroborated Disturbance){COLOR_RESET}"
    if decision == "T3":
        return f"{COLOR_RED}T3 (Critical Strike / Anchor){COLOR_RESET}"
    return f"{COLOR_MAGENTA}TX (High Uncertainty / Fault){COLOR_RESET}"


SCENARIO_MAP = {
    "1": TwinScenario.NORMAL_OPERATION,
    "normal": TwinScenario.NORMAL_OPERATION,
    "normal_operation": TwinScenario.NORMAL_OPERATION,
    "2": TwinScenario.APPROACHING_VESSEL,
    "approaching": TwinScenario.APPROACHING_VESSEL,
    "approaching_vessel": TwinScenario.APPROACHING_VESSEL,
    "3": TwinScenario.LOW_LEVEL_VIBRATION,
    "low_vibration": TwinScenario.LOW_LEVEL_VIBRATION,
    "low_level_vibration": TwinScenario.LOW_LEVEL_VIBRATION,
    "4": TwinScenario.INCREASING_DISTURBANCE,
    "increasing": TwinScenario.INCREASING_DISTURBANCE,
    "increasing_disturbance": TwinScenario.INCREASING_DISTURBANCE,
    "5": TwinScenario.SEVERE_DISTURBANCE,
    "severe": TwinScenario.SEVERE_DISTURBANCE,
    "severe_disturbance": TwinScenario.SEVERE_DISTURBANCE,
    "6": TwinScenario.SENSOR_DEGRADATION,
    "degradation": TwinScenario.SENSOR_DEGRADATION,
    "sensor_degradation": TwinScenario.SENSOR_DEGRADATION,
    "7": TwinScenario.RECOVERY,
    "recovery": TwinScenario.RECOVERY,
}


def run_demonstration(
    scenario: TwinScenario,
    mode: OperatingMode = OperatingMode.HYBRID_DEMO,
    seed: int = 42,
    duration_s: float = 25.0,
    dt: float = 0.3,
    playback_speed: float = 1.0,
    output_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Runs a complete digital twin demonstration."""
    simulator = DigitalTwinSimulator(seed=seed)
    simulator.set_scenario(scenario, seed=seed)

    engine = EarlyWarningEngine()

    # Create output directory
    if output_path is None:
        utc_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_dir = ROOT_DIR / "artifacts" / "digital_twin"
        out_dir.mkdir(parents=True, exist_ok=True)
        output_path = out_dir / f"demo_{scenario.value}_{mode.value.lower()}_{utc_str}.jsonl"
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print(">>> SUBSEA DIGITAL TWIN & MULTI-SENSOR EARLY WARNING DEMONSTRATOR <<<")
    print("=" * 80)
    print(f"  Scenario:        {scenario.value}")
    print(f"  Operating Mode:  {mode.value}")
    if mode == OperatingMode.HYBRID_DEMO:
        print(f"  {COLOR_BG_YELLOW} [!] SIMULATED DATA ACTIVE: Benchmark model channels synthesized. {COLOR_RESET}")
    else:
        print(f"  {COLOR_CYAN} [i] PHYSICAL ONLY: Simulated channels strictly filtered out. {COLOR_RESET}")
    print(f"  Random Seed:     {seed}")
    print(f"  Target Duration: {duration_s:.1f} s (dt={dt}s, {int(duration_s/dt)} steps)")
    print(f"  Event Log:       {output_path}")
    print("=" * 80)
    print(f"{'TIME':<7} | {'PHASE':<16} | {'EARLY WARNING':<22} | {'CONF':<6} | {'PIPELINE T0-TX':<18} | {'KEY METRICS'}")
    print("-" * 80)

    events: list[dict[str, Any]] = []
    n_steps = int(round(duration_s / dt))

    with open(output_path, "w", encoding="utf-8") as f_out:
        for step_idx in range(n_steps):
            frame = simulator.step(dt=dt)

            # Map readings: in physical-only mode, inject mock physical readings if hardware not connected
            readings = dict(frame.readings)

            if mode == OperatingMode.PHYSICAL_ONLY:
                # In physical-only demonstration without hardware, simulated readings are filtered out
                # Hardware readings are reported as disconnected/missing unless provided
                readings = {}

            # Evaluate Early Warning Engine
            warning_dec = engine.evaluate(
                readings=readings,
                mode=mode,
                timestamp=frame.timestamp,
                scenario_id=scenario.value,
            )

            # Evaluate Disturbance Pipeline Classification (T0-TX)
            # In simulation, derive benchmark T0-TX state from acoustic & kinematic parameters
            t_state = DecisionState.T0
            if mode == OperatingMode.PHYSICAL_ONLY:
                t_state = DecisionState.TX # Hardware disconnected
            else:
                rms = frame.summary.get("vibration_rms", 0.0)
                dist = frame.summary.get("distance_m", 100.0)
                if frame.readings.get("das_rms", {}).quality in (DataQuality.INVALID, DataQuality.STALE, DataQuality.MISSING):
                    t_state = DecisionState.TX
                elif rms > 1.5 and dist < 15.0:
                    t_state = DecisionState.T3
                elif rms > 0.40 and dist < 40.0:
                    t_state = DecisionState.T2
                elif rms > 0.40:
                    t_state = DecisionState.T1
                else:
                    t_state = DecisionState.T0

            record = {
                "step": step_idx,
                "timestamp": frame.timestamp,
                "elapsed_s": frame.elapsed_s,
                "scenario": scenario.value,
                "mode": mode.value,
                "phase": frame.phase,
                "early_warning": warning_dec.to_dict(),
                "disturbance_classification": t_state.value,
                "frame_summary": frame.summary,
            }
            events.append(record)
            f_out.write(json.dumps(record) + "\n")
            f_out.flush()

            # Formatted console output line
            t_str = f"{frame.elapsed_s:5.1f}s"
            phase_str = f"{frame.phase[:16]:<16}"
            warn_badge = format_warning_badge(warning_dec.state)
            conf_str = f"{warning_dec.confidence:4.2f}"
            dec_badge = format_decision_badge(t_state.value)
            metrics_str = (
                f"Dist: {frame.summary.get('distance_m', 0.0):4.1f}m | "
                f"RMS: {frame.summary.get('vibration_rms', 0.0):4.2f} | "
                f"Strain: {frame.summary.get('strain_microstrain', 0.0):5.1f}με"
            )

            print(f"{t_str} | {phase_str} | {warn_badge:<32} | {conf_str} | {dec_badge:<28} | {metrics_str}")

            if playback_speed > 0.0 and dt > 0:
                sleep_time = (dt / playback_speed)
                time.sleep(min(0.3, sleep_time))

    print("=" * 80)
    print(f"[OK] Demonstration finished successfully. {len(events)} steps recorded.")
    print(f"[OK] Detailed provenance log saved to: {output_path}")
    print("=" * 80)
    return events


def main() -> None:
    parser = argparse.ArgumentParser(description="AbyssLink Digital Twin Demonstrator")
    parser.add_argument(
        "--scenario",
        type=str,
        default="approaching_vessel",
        help="Scenario: 1-7 or normal, approaching, low_vibration, increasing, severe, degradation, recovery",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="hybrid",
        choices=["hybrid", "physical"],
        help="Operating mode: hybrid (default) or physical",
    )
    parser.add_argument("--seed", type=int, default=42, help="Deterministic random seed (default: 42)")
    parser.add_argument("--duration", type=float, default=20.0, help="Duration in seconds (default: 20.0)")
    parser.add_argument("--dt", type=float, default=0.3, help="Step time interval (default: 0.3s)")
    parser.add_argument("--speed", type=float, default=0.0, help="Playback speed multiplier (0.0 = max speed)")
    parser.add_argument("--output", type=str, default=None, help="Optional output JSONL file path")

    args = parser.parse_args()

    # Resolve scenario
    scen_key = args.scenario.lower()
    if scen_key not in SCENARIO_MAP:
        print(f"Error: Unknown scenario '{args.scenario}'. Choose from: {list(SCENARIO_MAP.keys())}")
        sys.exit(1)
    scenario = SCENARIO_MAP[scen_key]

    mode = OperatingMode.PHYSICAL_ONLY if args.mode.lower() == "physical" else OperatingMode.HYBRID_DEMO
    out_path = Path(args.output) if args.output else None

    run_demonstration(
        scenario=scenario,
        mode=mode,
        seed=args.seed,
        duration_s=args.duration,
        dt=args.dt,
        playback_speed=args.speed,
        output_path=out_path,
    )


if __name__ == "__main__":
    main()
