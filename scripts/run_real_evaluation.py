"""Run real-data validation for Marlinks and EMSO DAS datasets.

Generates:
- artifacts/real_data_evaluation/marlinks_manifest.json
- artifacts/real_data_evaluation/emso_manifest.json
- artifacts/real_data_evaluation/marlinks_spectral_response.png
- artifacts/real_data_evaluation/marlinks_spatial_energy_vs_distance.png
- artifacts/real_data_evaluation/marlinks_proximity_correlation.png
- artifacts/real_data_evaluation/emso_channel_statistics.png
- artifacts/real_data_evaluation/emso_temporal_stability.png
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import h5py
import matplotlib.pyplot as plt
import numpy as np

from subsea.real_evaluation import evaluate_emso_dataset, evaluate_marlinks_dataset



def generate_marlinks_plots(h5_path: Path, output_dir: Path, metrics: dict) -> None:
    with h5py.File(h5_path, "r") as f:
        X = f["X"][()]  # (60, 250, 100)
        y = f["y"][()]  # (60,)
        datetimes = [s.decode("utf-8") for s in f["datetimes"][:]]

    time_indices = np.arange(len(y))
    total_energy = X.sum(axis=(1, 2))
    cpa_idx = metrics["cpa_metrics"]["true_cpa_index"]
    peak_idx = metrics["cpa_metrics"]["peak_energy_index"]

    # 1. Spatial energy vs distance heatmap
    spatial_energy_t = X.sum(axis=-1)  # (60, 250)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True, gridspec_kw={"height_ratios": [2.5, 1]})

    channel_coords = np.arange(1440, 1440 + X.shape[1])
    im = ax1.imshow(
        spatial_energy_t.T,
        aspect="auto",
        origin="lower",
        extent=[0, 59, 1440, 1440 + 249],
        cmap="viridis",
    )
    cbar = fig.colorbar(im, ax=ax1, pad=0.02)
    cbar.set_label("Spectral Energy (arb. units)", fontsize=10)
    ax1.axvline(cpa_idx, color="red", linestyle="--", linewidth=1.5, label=f"True CPA (t={cpa_idx}, d={y[cpa_idx]:.1f}m)")
    ax1.axvline(peak_idx, color="cyan", linestyle=":", linewidth=1.5, label=f"Peak Energy (t={peak_idx}, d={y[peak_idx]:.1f}m)")
    ax1.set_ylabel("DAS Channel Index", fontsize=11)
    ax1.set_title("Marlinks Real DAS Spatial Energy Profile vs Container Ship Distance", fontsize=12, fontweight="bold")
    ax1.legend(loc="upper right", framealpha=0.9)

    ax2.plot(time_indices, y, color="tab:blue", linewidth=2, label="Vessel Distance y (m)")
    ax2.scatter([cpa_idx], [y[cpa_idx]], color="red", s=50, zorder=5)
    ax2.set_ylabel("Distance (m)", fontsize=11)
    ax2.set_xlabel("Time Step (10 s interval: 15:55:08 - 16:04:58 UTC)", fontsize=11)
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc="upper left")

    plt.tight_layout()
    fig.savefig(output_dir / "marlinks_spatial_energy_vs_distance.png", dpi=300)
    plt.close(fig)

    # 2. Spectral frequency response over time
    freq_energy_t = X.sum(axis=1)  # (60, 100)
    fig, ax = plt.subplots(figsize=(9, 6))
    im = ax.imshow(
        freq_energy_t.T,
        aspect="auto",
        origin="lower",
        extent=[0, 59, 0, 100],
        cmap="inferno",
    )
    cbar = fig.colorbar(im, ax=ax, pad=0.02)
    cbar.set_label("Acoustic Power Across Bins", fontsize=10)
    ax.axvline(cpa_idx, color="cyan", linestyle="--", linewidth=1.5, label=f"True CPA (t={cpa_idx})")
    ax.set_title("Marlinks DAS Frequency Band Energy Response vs Time", fontsize=12, fontweight="bold")
    ax.set_ylabel("Frequency Feature Bin Index (0-99)", fontsize=11)
    ax.set_xlabel("Time Step (10 s interval)", fontsize=11)
    ax.legend(loc="upper right")
    plt.tight_layout()
    fig.savefig(output_dir / "marlinks_spectral_response.png", dpi=300)
    plt.close(fig)

    # 3. Proximity correlation scatter & fit
    inv_y = 1000.0 / y  # km^-1
    rho = metrics["correlation_metrics"]["spearman_rho_energy_vs_inverse_dist"]
    p_rho = metrics["correlation_metrics"]["spearman_p_energy_vs_inverse_dist"]
    r_pearson = metrics["correlation_metrics"]["pearson_r_energy_vs_inverse_dist"]

    fig, ax = plt.subplots(figsize=(8, 6))
    scatter = ax.scatter(
        inv_y,
        total_energy * 1e7,
        c=time_indices,
        cmap="coolwarm",
        s=45,
        edgecolor="k",
        alpha=0.85,
    )
    cbar = fig.colorbar(scatter, ax=ax)
    cbar.set_label("Time Sequence Step (0 -> 59)", fontsize=10)

    # Annotations
    ax.set_xlabel(r"Inverse Vessel Distance $1/y$ ($\times 10^{-3} \text{ m}^{-1}$)", fontsize=11)
    ax.set_ylabel(r"Total DAS Acoustic Energy ($\times 10^{-7}$)", fontsize=11)
    ax.set_title("Marlinks DAS Acoustic Energy vs Inverse Vessel Distance", fontsize=12, fontweight="bold")
    ax.annotate(
        f"Spearman rank $\\rho = {rho:.4f}$\n$p = {p_rho:.2e}$\nPearson $r = {r_pearson:.4f}$",
        xy=(0.05, 0.78),
        xycoords="axes fraction",
        bbox=dict(boxstyle="round,pad=0.5", fc="white", ec="gray", alpha=0.9),
        fontsize=10,
    )
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    fig.savefig(output_dir / "marlinks_proximity_correlation.png", dpi=300)
    plt.close(fig)


def generate_emso_plots(npy_path: Path, output_dir: Path, metrics: dict) -> None:
    data = np.load(npy_path)
    time_steps, channel_count = data.shape

    # 1. Channel RMS profile
    channel_rms = np.sqrt(np.mean(data**2, axis=0))
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(np.arange(channel_count), channel_rms, color="#1f77b4", linewidth=0.8, alpha=0.8)
    median_rms = metrics["channel_rms_statistics"]["median_rms"]
    mean_rms = metrics["channel_rms_statistics"]["mean_rms"]
    ax.axhline(median_rms, color="red", linestyle="--", label=f"Median RMS = {median_rms:.1f}")
    ax.axhline(mean_rms, color="orange", linestyle=":", label=f"Mean RMS = {mean_rms:.1f}")
    ax.set_title("EMSO Western Ionian Deep-Sea DAS Channel RMS Distribution (2,963 Channels)", fontsize=12, fontweight="bold")
    ax.set_xlabel("Fiber Optical Sensing Channel Index", fontsize=11)
    ax.set_ylabel("Optical Phase Strain RMS", fontsize=11)
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper right")
    plt.tight_layout()
    fig.savefig(output_dir / "emso_channel_statistics.png", dpi=300)
    plt.close(fig)

    # 2. Temporal stability waveform & window RMS
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7))

    # Waveform of a representative channel
    rep_channel = int(np.argsort(channel_rms)[len(channel_rms) // 2])
    t_seconds = np.arange(time_steps) / 10.0
    ax1.plot(t_seconds, data[:, rep_channel], color="#2ca02c", linewidth=0.7)
    ax1.set_title(f"EMSO Ambient Seafloor Baseline Waveform (Channel {rep_channel}, Duration: 1050 s)", fontsize=11, fontweight="bold")
    ax1.set_xlabel("Time (seconds)", fontsize=10)
    ax1.set_ylabel("Amplitude", fontsize=10)
    ax1.grid(True, alpha=0.3)

    # Window RMS
    windows = metrics["temporal_stability"]["window_rms_values"]
    window_centers = (np.arange(len(windows)) + 0.5) * 105.0
    cv = metrics["temporal_stability"]["temporal_stability_cv"]
    ax2.plot(window_centers, windows, marker="o", color="#d62728", linewidth=1.5)
    ax2.set_title(f"Temporal Baseline Stability Across 105-second Windows (CV = {cv:.4%})", fontsize=11, fontweight="bold")
    ax2.set_xlabel("Time Center (seconds)", fontsize=10)
    ax2.set_ylabel("Window RMS", fontsize=10)
    ax2.set_ylim(min(windows) * 0.998, max(windows) * 1.002)
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    fig.savefig(output_dir / "emso_temporal_stability.png", dpi=300)
    plt.close(fig)


def main() -> None:
    output_dir = Path("artifacts/real_data_evaluation")
    output_dir.mkdir(parents=True, exist_ok=True)

    marlinks_path = Path("data/marlinks_demo/reduced_dataset_sensor_range_1440_1690.h5")
    emso_path = Path("data/emso_ionian/decimated_20250610T030504.010529_1050_seconds_10_Hz.npy")

    print(f"Evaluating Marlinks: {marlinks_path}...")
    marlinks_metrics = evaluate_marlinks_dataset(marlinks_path)
    marlinks_manifest = {
        "status": "EXECUTED",
        "configuration": {
            "dataset": "Marlinks Offshore Wind Farm DAS Demo",
            "base_channel": 1440,
            "interaction_radius_m": 500.0,
        },
        "results": marlinks_metrics,
    }
    with open(output_dir / "marlinks_manifest.json", "w", encoding="utf-8") as f:
        json.dump(marlinks_manifest, f, indent=2)
    print("Saved Marlinks manifest.")

    print("Generating Marlinks plots...")
    generate_marlinks_plots(marlinks_path, output_dir, marlinks_metrics)
    print("Saved Marlinks plots.")

    print(f"\nEvaluating EMSO: {emso_path}...")
    emso_metrics = evaluate_emso_dataset(emso_path)
    emso_manifest = {
        "status": "EXECUTED",
        "configuration": {
            "dataset": "EMSO Western Ionian Seafloor Observatory DAS",
            "sampling_rate_hz": 10.0,
            "n_stability_windows": 10,
        },
        "results": emso_metrics,
    }
    with open(output_dir / "emso_manifest.json", "w", encoding="utf-8") as f:
        json.dump(emso_manifest, f, indent=2)
    print("Saved EMSO manifest.")

    print("Generating EMSO plots...")
    generate_emso_plots(emso_path, output_dir, emso_metrics)
    print("Saved EMSO plots.")
    print("\nReal evaluation complete!")


if __name__ == "__main__":
    main()
