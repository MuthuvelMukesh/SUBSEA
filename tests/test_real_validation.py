from pathlib import Path
import numpy as np
import pytest

from subsea.das import DasSchema, load_das_hdf5, load_das_numpy
from subsea.real_data import load_dataset
from subsea.real_evaluation import compute_gini, evaluate_emso_dataset, evaluate_marlinks_dataset


def test_compute_gini():
    # Uniform distribution -> Gini near 0
    uniform = np.ones(100)
    assert compute_gini(uniform) == pytest.approx(0.0, abs=1e-3)

    # Highly concentrated distribution -> Gini near 1
    concentrated = np.zeros(100)
    concentrated[0] = 1000.0
    assert compute_gini(concentrated) > 0.95


def test_load_das_hdf5_3d_and_iso_timestamp(tmp_path):
    h5py = pytest.importorskip("h5py")
    test_h5 = tmp_path / "test_3d.h5"
    with h5py.File(test_h5, "w") as f:
        # (3 time steps, 4 channels, 5 frequency bins)
        data = np.ones((3, 4, 5), dtype=np.float64) * 2.0
        f.create_dataset("X", data=data)
        f.create_dataset(
            "datetimes",
            data=[
                b"2026-01-01 00:00:00+00:00",
                b"2026-01-01 00:00:10+00:00",
                b"2026-01-01 00:00:20+00:00",
            ],
        )
        f.create_dataset("dist", data=[100.0, 50.0, 20.0])

    schema = DasSchema(signal_path="X", timestamp_path="datetimes", distance_path="dist")
    dataset = load_das_hdf5(test_h5, schema)

    assert len(dataset.samples) == 3
    assert dataset.channel_count == 4
    # Mean of ones * 2.0 along axis -1 is 2.0
    assert dataset.samples[0][0] == pytest.approx(2.0)
    assert dataset.timestamps[1] - dataset.timestamps[0] == pytest.approx(10.0)
    assert dataset.vessel_distances == (100.0, 50.0, 20.0)
    assert dataset.provenance.causal_ground_truth is False


def test_load_das_numpy_contract(tmp_path):
    test_npy = tmp_path / "test_das.npy"
    data = np.arange(12, dtype=np.float32).reshape(4, 3)  # 4 time steps, 3 channels
    np.save(test_npy, data)

    dataset = load_das_numpy(test_npy, sampling_rate_hz=2.0, start_timestamp=10.0)

    assert len(dataset.samples) == 4
    assert dataset.channel_count == 3
    assert dataset.timestamps == (10.0, 10.5, 11.0, 11.5)
    assert dataset.provenance.format == "das_numpy"
    assert dataset.provenance.causal_ground_truth is False


def test_load_dataset_numpy_format(tmp_path):
    test_npy = tmp_path / "array.npy"
    np.save(test_npy, np.array([[1.0, 2.0], [3.0, 4.0]]))

    loaded = load_dataset(test_npy)
    assert len(loaded.records) == 2
    assert loaded.provenance.format == "numpy"
    assert loaded.records[0]["value"] == [1.0, 2.0]


def test_marlinks_evaluation_execution():
    marlinks_file = Path("data/marlinks_demo/reduced_dataset_sensor_range_1440_1690.h5")
    if not marlinks_file.is_file():
        pytest.skip("Marlinks demo file not present")

    metrics = evaluate_marlinks_dataset(marlinks_file)

    assert metrics["status"] == "EXECUTED"
    assert metrics["sample_count"] == 60
    assert metrics["channel_count"] == 250
    assert metrics["frequency_bins"] == 100
    assert metrics["cpa_metrics"]["true_cpa_index"] == 26
    assert metrics["cpa_metrics"]["true_cpa_distance_m"] == pytest.approx(26.22, abs=0.01)
    # Correlation between acoustic energy and inverse distance must be positive and strong
    assert metrics["correlation_metrics"]["spearman_rho_energy_vs_inverse_dist"] > 0.90
    assert metrics["spatial_localization"]["spatial_gini_coefficient"] > 0.70
    assert metrics["monotonicity"]["approach_energy_spearman"] > 0.95


def test_emso_evaluation_execution():
    emso_file = Path("data/emso_ionian/decimated_20250610T030504.010529_1050_seconds_10_Hz.npy")
    if not emso_file.is_file():
        pytest.skip("EMSO Ionian file not present")

    metrics = evaluate_emso_dataset(emso_file)

    assert metrics["status"] == "EXECUTED"
    assert metrics["sample_count"] == 10500
    assert metrics["channel_count"] == 2963
    assert metrics["sampling_rate_hz"] == 10.0
    assert metrics["channel_rms_statistics"]["mean_rms"] > 0.0
    # Temporal stability CV across 10 windows must be tightly stationary (< 1%)
    assert metrics["temporal_stability"]["temporal_stability_cv"] < 0.01
