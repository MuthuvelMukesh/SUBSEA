from __future__ import annotations

import argparse
from pathlib import Path

from subsea.baselines import METHODS
from subsea.experiments import run_method_comparison


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare interpretable baselines and ablations")
    parser.add_argument("--scenario", action="append", dest="scenarios", default=None)
    parser.add_argument("--trials", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--method", action="append", dest="methods", choices=sorted(METHODS), default=None)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    scenarios = args.scenarios or ["S01", "S02", "S04", "S05"]
    methods = tuple(args.methods or sorted(METHODS))
    print(run_method_comparison(scenarios, args.trials, args.seed, args.output, methods=methods))


if __name__ == "__main__":
    main()
