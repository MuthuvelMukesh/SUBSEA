#!/usr/bin/env python3
"""Run single or all-scenario simulations."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from subsea.experiments import run_all_scenarios, run_method_comparison
from subsea.simulation import SUPPORTED_SCENARIOS


def main() -> None:
    parser = argparse.ArgumentParser(description="Run scenario simulations")
    parser.add_argument("--scenario", action="append", default=None)
    parser.add_argument("--all-scenarios", action="store_true")
    parser.add_argument("--trials", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)

    if args.all_scenarios:
        print(f"[all scenarios] trials={args.trials}")
        path = run_all_scenarios(args.trials, args.seed, output)
    else:
        scenarios = args.scenario or ["S04"]
        print(f"[scenarios] {scenarios} trials={args.trials}")
        path = run_method_comparison(scenarios, args.trials, args.seed, output)
    print(f"Manifest: {path}")


if __name__ == "__main__":
    main()
