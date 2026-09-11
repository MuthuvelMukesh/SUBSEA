from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .pipeline import run_pipeline
from .simulation import generate_observations, make_scenario, scenario_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a reproducible subsea disturbance simulation")
    parser.add_argument("--scenario", default="S04")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output")
    args = parser.parse_args()
    scenario = make_scenario(args.scenario, args.seed)
    observations, vessel = generate_observations(scenario)
    result = run_pipeline(observations, vessel, environmental_event=scenario.environmental_event)
    payload = {"scenario": scenario_manifest(scenario), "decision": asdict(result)}
    text = json.dumps(payload, indent=2, default=str)
    if args.output:
        output_path = Path(args.output)
        if output_path.exists():
            raise FileExistsError(f"refusing to overwrite existing result: {output_path}")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as output:
            output.write(text + "\n")
    else:
        print(text)


if __name__ == "__main__":
    main()
