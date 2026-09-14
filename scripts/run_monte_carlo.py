#!/usr/bin/env python3
"""Run reproducible Monte Carlo experiments."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from subsea.experiments import run_monte_carlo
from subsea.simulation import SUPPORTED_SCENARIOS


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Monte Carlo experiments")
    parser.add_argument("--scenario", action="append", default=None,
                        help="Scenario IDs (repeatable). Default: all.")
    parser.add_argument("--trials", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", required=True)
    parser.add_argument("--attack", default="none")
    parser.add_argument("--severity", type=float, default=0.0)
    parser.add_argument("--methods", nargs="+", default=["proposed"])
    args = parser.parse_args()
    scenarios = args.scenario if args.scenario else sorted(SUPPORTED_SCENARIOS)
    output = Path(args.output)

    print(f"[Monte Carlo] scenarios={scenarios} trials={args.trials} seed={args.seed}")
    path = run_monte_carlo(
        scenarios, args.trials, args.seed, output,
        methods=tuple(args.methods),
        attack=args.attack,
        attack_severity=args.severity,
    )
    print(f"Manifest: {path}")
    print("Monte Carlo complete.")


if __name__ == "__main__":
    main()
