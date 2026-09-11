from __future__ import annotations

import argparse
from pathlib import Path

from subsea.reporting import generate_paper_outputs


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate tables and figures from an executed method manifest")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(generate_paper_outputs(args.manifest, args.output))


if __name__ == "__main__":
    main()
