from __future__ import annotations

import argparse
from pathlib import Path

from subsea.experiments import run_attack_severity_sweep


def main() -> None:
    parser = argparse.ArgumentParser(description="Run an adversarial attack severity sweep")
    parser.add_argument("--scenario", default="S04")
    parser.add_argument("--attack", default="ais_spoofing", choices=["ais_spoofing", "transponder_suppression", "timestamp_manipulation"])
    parser.add_argument("--trials", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(run_attack_severity_sweep(args.scenario, args.trials, args.seed, args.output, attack=args.attack))


if __name__ == "__main__":
    main()
