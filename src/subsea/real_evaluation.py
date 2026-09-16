from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats

from .das import DasSchema, load_das_hdf5, load_das_numpy


def compute_gini(values: np.ndarray) -> float:
    """Compute Gini coefficient of an array to quantify concentration."""
    arr = np.asarray(values, dtype=np.float64).flatten()
    if len(arr) == 0 or np.all(arr == 0):
        return 0.0
    arr = np.abs(arr)
    sorted_arr = np.sort(arr)
    n = len(sorted_arr)
    index = np.arange(1, n + 1)
    total = np.sum(sorted_arr)
    if total == 0:
        return 0.0
    return float(np.sum((2 * index - n - 1) * sorted_arr) / (n * total))


def evaluate_marlinks_dataset(
    path: str | Path,
    *,
    base_channel: int = 1440,
) -> dict[str, Any]:
    """Evaluate Marlinks DAS dataset on genuine physical proximity and spectral fields.

    Validates:
    - 3D spectral feature energy across time and space
    - CPA alignment between acoustic peak and distance minimum
    - Pearson and Spearman correlations between energy and distance/proximity
    - Spatial concentration metrics (Gini, Peak-to-Average ratio)
    - Approach and departure monotonicity

    NO 2D trajectory reconstruction, NO causal threat labels, NO fabricated F1.
    """
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(file_path)

    import h5py

    with h5py.File(file_path, "r") as handle:
        if "X" not in handle or "y" not in handle or "datetimes" not in handle:
            raise KeyError("Marlinks HDF5 file missing required X, y, or datetimes dataset")
        X = handle["X"][()]  # shape: (60, 250, 100)
        y = handle["y"][()]  # shape: (60,)
        raw_dt = handle["datetimes"][()]
        timestamps = [
            val.decode("utf-8") if isinstance(val, (bytes, bytearray)) else str(val)
            for val in raw_dt
        ]
        ship_beam = float(handle["ship_info/beam"][0]) if "ship_info/beam" in handle else None
        ship_length = float(handle["ship_info/length"][0]) if "ship_info/length" in handle else None
        ship_type_raw = handle["ship_info/type"][0] if "ship_info/type" in handle else None
        ship_type = (
            ship_type_raw.decode("utf-8")
            if isinstance(ship_type_raw, (bytes, bytearray))
            else str(ship_type_raw)
        )

    # Validate finite values
    if not np.all(np.isfinite(X)) or not np.all(np.isfinite(y)):
        raise ValueError("Marlinks dataset contains non-finite values")

    # 1. Temporal energy profiles
    total_energy_t = X.sum(axis=(1, 2))  # (60,)
    mean_energy_t = X.mean(axis=(1, 2))

    # 2. Distance correlations
    inv_y = 1.0 / np.maximum(y, 1e-6)
    neg_y = -y

    r_inv, p_inv = stats.pearsonr(total_energy_t, inv_y)
    rho_inv, p_rho_inv = stats.spearmanr(total_energy_t, inv_y)
    r_neg, p_neg = stats.pearsonr(total_energy_t, neg_y)
    rho_neg, p_rho_neg = stats.spearmanr(total_energy_t, neg_y)

    # 3. CPA alignment
    idx_min_y = int(np.argmin(y))
    idx_max_energy = int(np.argmax(total_energy_t))
    cpa_true_dist = float(y[idx_min_y])
    dist_at_max_energy = float(y[idx_max_energy])
    cpa_time_offset_s = float(abs(idx_max_energy - idx_min_y) * 10.0)

    # 4. Spatial localization at CPA
    channel_energy_cpa = X[idx_min_y].sum(axis=-1)  # (250,)
    peak_channel_local_idx = int(np.argmax(channel_energy_cpa))
    peak_channel_id = base_channel + peak_channel_local_idx
    spatial_gini = compute_gini(channel_energy_cpa)
    mean_ce = float(np.mean(channel_energy_cpa))
    par = float(np.max(channel_energy_cpa) / mean_ce) if mean_ce > 0 else 0.0

    # 5. Monotonicity
    # Approach phase: from start up to true CPA
    approach_steps = np.arange(idx_min_y + 1)
    spearman_approach_dist, _ = stats.spearmanr(approach_steps, y[: idx_min_y + 1])
    spearman_approach_energy, _ = stats.spearmanr(approach_steps, total_energy_t[: idx_min_y + 1])

    # Departure phase: from true CPA to end
    departure_steps = np.arange(len(y) - idx_min_y)
    spearman_depart_dist, _ = stats.spearmanr(departure_steps, y[idx_min_y:])
    spearman_depart_energy, _ = stats.spearmanr(departure_steps, total_energy_t[idx_min_y:])

    # 6. Physical proximity confidence (1D mapping)
    interaction_radius_m = 500.0
    c_p_1d = np.clip(1.0 - y / interaction_radius_m, 0.0, 1.0)
    energy_norm = total_energy_t / np.max(total_energy_t)
    r_cp, _ = stats.pearsonr(energy_norm, c_p_1d)

    digest = hashlib.sha256(file_path.read_bytes()).hexdigest()

    return {
        "dataset_name": "Marlinks Offshore Wind Farm DAS Demo",
        "file_path": str(file_path),
        "sha256": digest,
        "sample_count": len(y),
        "channel_count": int(X.shape[1]),
        "frequency_bins": int(X.shape[2]),
        "time_start": timestamps[0],
        "time_end": timestamps[-1],
        "ship_info": {
            "type": ship_type,
            "length_m": ship_length,
            "beam_m": ship_beam,
        },
        "cpa_metrics": {
            "true_cpa_index": idx_min_y,
            "true_cpa_timestamp": timestamps[idx_min_y],
            "true_cpa_distance_m": cpa_true_dist,
            "peak_energy_index": idx_max_energy,
            "peak_energy_timestamp": timestamps[idx_max_energy],
            "distance_at_peak_energy_m": dist_at_max_energy,
            "cpa_time_offset_seconds": cpa_time_offset_s,
        },
        "correlation_metrics": {
            "pearson_r_energy_vs_inverse_dist": float(r_inv),
            "pearson_p_energy_vs_inverse_dist": float(p_inv),
            "spearman_rho_energy_vs_inverse_dist": float(rho_inv),
            "spearman_p_energy_vs_inverse_dist": float(p_rho_inv),
            "pearson_r_energy_vs_negative_dist": float(r_neg),
            "spearman_rho_energy_vs_negative_dist": float(rho_neg),
            "pearson_r_energy_vs_1d_cp": float(r_cp),
        },
        "spatial_localization": {
            "peak_sensor_channel": peak_channel_id,
            "peak_channel_index": peak_channel_local_idx,
            "spatial_gini_coefficient": spatial_gini,
            "peak_to_average_ratio": par,
        },
        "monotonicity": {
            "approach_distance_spearman": float(spearman_approach_dist),
            "approach_energy_spearman": float(spearman_approach_energy),
            "departure_distance_spearman": float(spearman_depart_dist),
            "departure_energy_spearman": float(spearman_depart_energy),
        },
        "status": "EXECUTED",
    }


def evaluate_emso_dataset(
    path: str | Path,
    *,
    sampling_rate_hz: float = 10.0,
    n_stability_windows: int = 10,
) -> dict[str, Any]:
    """Evaluate EMSO submarine DAS dataset on noise floor, stability, and channel variability.

    Validates:
    - Real submarine optical fiber DAS channel RMS and variance
    - Inter-channel variability across 2,963 channels
    - Temporal baseline stability over 1,050 seconds
    - Statistical distribution (kurtosis, skewness) of acoustic strain noise floor

    NO vessel detection or AIS association is claimed.
    """
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(file_path)
    if file_path.suffix.lower() != ".npy":
        raise ValueError("EMSO dataset requires a .npy file")

    data = np.load(file_path)
    if data.ndim != 2:
        raise ValueError("EMSO array must be 2-dimensional")

    time_steps, channel_count = data.shape
    duration_s = float(time_steps / sampling_rate_hz)

    # 1. Channel statistics
    channel_rms = np.sqrt(np.mean(data**2, axis=0))
    channel_std = np.std(data, axis=0)

    mean_rms = float(np.mean(channel_rms))
    median_rms = float(np.median(channel_rms))
    std_rms = float(np.std(channel_rms))
    min_rms = float(np.min(channel_rms))
    max_rms = float(np.max(channel_rms))
    inter_channel_cv = float(std_rms / mean_rms) if mean_rms > 0 else 0.0

    # 2. Temporal stability across windows
    window_len = time_steps // n_stability_windows
    window_rms_list = []
    for w in range(n_stability_windows):
        segment = data[w * window_len : (w + 1) * window_len]
        w_rms = float(np.sqrt(np.mean(segment**2)))
        window_rms_list.append(w_rms)

    window_rms_arr = np.array(window_rms_list)
    mean_window_rms = float(np.mean(window_rms_arr))
    temporal_stability_cv = (
        float(np.std(window_rms_arr) / mean_window_rms) if mean_window_rms > 0 else 0.0
    )

    # 3. Distribution statistics
    sample_sub = data.ravel()[::100]  # sample 1/100 for speed
    kurt = float(stats.kurtosis(sample_sub))
    skew = float(stats.skew(sample_sub))

    digest = hashlib.sha256(file_path.read_bytes()).hexdigest()

    return {
        "dataset_name": "EMSO Western Ionian Seafloor Observatory DAS",
        "file_path": str(file_path),
        "sha256": digest,
        "sample_count": time_steps,
        "channel_count": channel_count,
        "sampling_rate_hz": sampling_rate_hz,
        "duration_seconds": duration_s,
        "channel_rms_statistics": {
            "mean_rms": mean_rms,
            "median_rms": median_rms,
            "std_rms": std_rms,
            "min_rms": min_rms,
            "max_rms": max_rms,
            "inter_channel_cv": inter_channel_cv,
        },
        "temporal_stability": {
            "windows_evaluated": n_stability_windows,
            "window_duration_seconds": float(window_len / sampling_rate_hz),
            "window_rms_values": window_rms_list,
            "temporal_stability_cv": temporal_stability_cv,
        },
        "distribution_metrics": {
            "sample_kurtosis": kurt,
            "sample_skewness": skew,
        },
        "status": "EXECUTED",
    }
