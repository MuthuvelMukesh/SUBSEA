#!/usr/bin/env python3
"""Run robustness sweeps: noise, packet loss, position uncertainty."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from subsea.experiments import (
    run_noise_sweep, run_packet_loss_sweep, run_position_uncertainty_sweep,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run robustness parameter sweeps")
    parser.add_argument("--scenario", default="S04")
    parser.add_argument("--trials", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)

    print(f"[noise sweep] scenario={args.scenario} trials={args.trials}")
    noise_path = run_noise_sweep(args.scenario, args.trials, args.seed, output / "noise")
    print(f"  -> {noise_path}")

    print(f"[packet-loss sweep] scenario={args.scenario} trials={args.trials}")
    pl_path = run_packet_loss_sweep(args.scenario, args.trials, args.seed, output / "packet_loss")
    print(f"  -> {pl_path}")

    print(f"[position-uncertainty sweep] scenario={args.scenario} trials={args.trials}")
    pu_path = run_position_uncertainty_sweep(args.scenario, args.trials, args.seed, output / "position_uncertainty")
    print(f"  -> {pu_path}")

    print("Robustness sweeps complete.")


if __name__ == "__main__":
    main()
