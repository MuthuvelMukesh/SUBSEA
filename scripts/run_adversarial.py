from __future__ import annotations

import argparse
from pathlib import Path

from subsea.experiments import run_trials


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a seeded vessel-side adversarial experiment")
    parser.add_argument("--scenario", default="S04")
    parser.add_argument("--attack", choices=["none", "ais_spoofing", "transponder_suppression", "timestamp_manipulation"] , default="ais_spoofing")
    parser.add_argument("--severity", type=float, default=1.0)
    parser.add_argument("--trials", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = run_trials(args.scenario, args.trials, args.seed, args.output, attack=args.attack, attack_severity=args.severity)
    print(manifest)


if __name__ == "__main__":
    main()
