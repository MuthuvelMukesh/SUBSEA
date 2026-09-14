from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from subsea.reporting import (
    generate_paper_outputs,
    generate_ablation_figure,
    generate_ablation_table,
    generate_adversarial_figures,
    generate_adversarial_table,
    generate_robustness_figure,
    generate_robustness_table,
    generate_calibration_figure,
    generate_calibration_table,
)
from subsea.experiments import (
    run_method_comparison,
    run_ablation_study,
    run_calibration_analysis,
    run_attack_severity_sweep,
    run_noise_sweep,
    run_packet_loss_sweep,
)
from subsea.simulation import SUPPORTED_SCENARIOS


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate publication tables and figures from executed manifests")
    parser.add_argument("--manifest", type=Path, help="Path to executed baseline/comparison manifest")
    parser.add_argument("--ablation-manifest", type=Path, help="Path to executed ablation study manifest")
    parser.add_argument("--adversarial-manifest", type=Path, help="Path to executed adversarial sweep manifest")
    parser.add_argument("--noise-manifest", type=Path, help="Path to executed noise sweep manifest")
    parser.add_argument("--packet-loss-manifest", type=Path, help="Path to executed packet loss sweep manifest")
    parser.add_argument("--calibration-manifest", type=Path, help="Path to executed calibration manifest")
    parser.add_argument("--output", type=Path, default=Path("artifacts/paper_results"), help="Output directory for publication tables and figures")
    parser.add_argument("--run-suite", action="store_true", help="Execute complete reproducible suite (all S01-S22, baselines, ablations, sweeps, calibration) and generate all figures/tables")
    parser.add_argument("--trials", type=int, default=5, help="Number of trials per scenario if --run-suite is used")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducible execution")

    args = parser.parse_args()
    out_dir = args.output
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.run_suite:
        print(f"Executing complete reproducible research suite (seed={args.seed}, trials={args.trials})...")
        scenarios = sorted(SUPPORTED_SCENARIOS)
        
        # 1. Baseline comparison
        print("-> Running baseline comparison...")
        manifest_path = run_method_comparison(scenarios, args.trials, args.seed, out_dir / "manifest_baselines")
        args.manifest = manifest_path
        
        # 2. Ablation study
        print("-> Running ablation study...")
        abl_path = run_ablation_study(scenarios, args.trials, args.seed, out_dir / "manifest_ablation")
        args.ablation_manifest = abl_path
        
        # 3. Calibration analysis
        print("-> Running calibration analysis...")
        cal_path = run_calibration_analysis(scenarios, args.trials, args.seed, out_dir / "manifest_calibration")
        args.calibration_manifest = cal_path
        
        # 4. Adversarial sweep
        print("-> Running adversarial sweep...")
        adv_path = run_attack_severity_sweep("S04", args.trials, args.seed, out_dir / "manifest_adversarial", attack="ais_spoofing", severities=(0.0, 0.25, 0.5, 0.75, 1.0))
        args.adversarial_manifest = adv_path
        
        # 5. Robustness sweeps
        print("-> Running noise sweep...")
        noise_path = run_noise_sweep("S04", args.trials, args.seed, out_dir / "manifest_noise")
        args.noise_manifest = noise_path
        
        print("-> Running packet-loss sweep...")
        pl_path = run_packet_loss_sweep("S04", args.trials, args.seed, out_dir / "manifest_packet_loss")
        args.packet_loss_manifest = pl_path

    if not args.manifest:
        parser.error("Either --manifest or --run-suite must be specified.")

    print(f"Generating core paper outputs from {args.manifest} to {out_dir}...")
    summary = generate_paper_outputs(args.manifest, out_dir / "core")

    # Additional figures & tables if manifests available
    if args.ablation_manifest and args.ablation_manifest.is_file():
        print("-> Generating Ablation Figure 5 & Table V...")
        generate_ablation_figure(args.ablation_manifest, out_dir / "core")
        generate_ablation_table(args.ablation_manifest, out_dir / "core")

    if args.adversarial_manifest and args.adversarial_manifest.is_file():
        print("-> Generating Adversarial Figures 6-7 & Table VI...")
        generate_adversarial_figures(args.adversarial_manifest, out_dir / "core")
        generate_adversarial_table(args.adversarial_manifest, out_dir / "core")

    if args.noise_manifest and args.noise_manifest.is_file():
        print("-> Generating Noise Robustness Figure 8 & Table VII...")
        generate_robustness_figure(args.noise_manifest, out_dir / "core", "noise")
        pl_p = args.packet_loss_manifest or Path("nonexistent")
        generate_robustness_table(args.noise_manifest, pl_p, out_dir / "core")

    if args.packet_loss_manifest and args.packet_loss_manifest.is_file():
        print("-> Generating Packet-Loss Robustness Figure 8...")
        generate_robustness_figure(args.packet_loss_manifest, out_dir / "core", "packet_loss")

    if args.calibration_manifest and args.calibration_manifest.is_file():
        print("-> Generating Calibration Figure 9 & Table VIII...")
        generate_calibration_figure(args.calibration_manifest, out_dir / "core")
        generate_calibration_table(args.calibration_manifest, out_dir / "core")

    print(f"Successfully generated all publication artifacts in {out_dir / 'core'}!")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
