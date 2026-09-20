"""Tests for Dryad Oliktok Submarine DAS dataset adapter and evaluation."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import pytest

from subsea.oliktok import OliktokAdapter, load_oliktok_dataset
from subsea.oliktok_evaluation import evaluate_oliktok_dataset


@pytest.fixture
def oliktok_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "Dryad_Oliktok"


@pytest.fixture
def primary_nc_path(oliktok_dir: Path) -> Path:
    return oliktok_dir / "oliktok_das_mooring_hourly_dataset.nc"


def test_oliktok_file_exists_if_present(primary_nc_path: Path):
    assert primary_nc_path.is_file(), f"Primary Oliktok file missing: {primary_nc_path}"


def test_oliktok_metadata(primary_nc_path: Path):
    ds = OliktokAdapter.load(primary_nc_path)
    assert ds.file_name == "oliktok_das_mooring_hourly_dataset.nc"
    assert ds.format == "NetCDF-4 / HDF5"
    assert ds.scientific_role == "environmental / real DAS robustness validation"
    assert ds.frequency_bins == 32
    assert ds.frequencies[0] == pytest.approx(0.0078125, abs=1e-5)
    assert ds.frequencies[-1] == pytest.approx(0.494140625, abs=1e-5)
    assert ds.has_wave_reference is True
    assert ds.wave_height_mean is not None
    assert 0.2 <= ds.wave_height_mean <= 2.0


def test_oliktok_shape(primary_nc_path: Path):
    ds = OliktokAdapter.load(primary_nc_path)
    assert ds.temporal_samples == 215
    assert ds.channel_count == 183
    assert len(ds.channel_ids) == 183
    assert len(ds.integrated_channel_rms) == 215
    assert all(len(row) == 183 for row in ds.integrated_channel_rms)


def test_oliktok_sampling_rate(primary_nc_path: Path):
    ds = OliktokAdapter.load(primary_nc_path)
    assert ds.sampling_interval_hours == 1.0
    # 215 hours = 214 intervals between first and last sample -> 214 * 3600 = 770400 s
    # Total time span from 0 to 663 hours = 2,386,800 s
    assert ds.duration_seconds == pytest.approx(2386800.0, abs=1.0)
    assert ds.duration_seconds / 86400.0 == pytest.approx(27.625, abs=0.01)


def test_oliktok_timestamp_order(primary_nc_path: Path):
    ds = OliktokAdapter.load(primary_nc_path)
    timestamps = ds.timestamps_unix
    assert len(timestamps) == 215
    assert all(right >= left for left, right in zip(timestamps[:-1], timestamps[1:]))
    assert ds.timestamps_iso[0].startswith("2023-08-24T04:00:00")
    assert ds.timestamps_iso[-1].startswith("2023-09-20T19:00:00")


def test_oliktok_no_unexpected_nan_inf(primary_nc_path: Path):
    ds = OliktokAdapter.load(primary_nc_path)
    for row in ds.integrated_channel_rms:
        for val in row:
            assert not math.isnan(val)
            assert not math.isinf(val)
            assert val > 0.0


import math


def test_oliktok_provenance_hash(primary_nc_path: Path):
    root = Path(__file__).resolve().parent.parent
    prov_p = root / "data" / "PROVENANCE.json"
    prov_data = json.loads(prov_p.read_text(encoding="utf-8"))

    oliktok_rec = [r for r in prov_data["provenance_records"] if r["dataset_name"] == "Dryad Oliktok submarine DAS"][0]
    expected_hash = oliktok_rec["files_metadata"]["oliktok_das_mooring_hourly_dataset.nc"]["sha256"]

    computed_hash = hashlib.sha256(primary_nc_path.read_bytes()).hexdigest()
    assert computed_hash == expected_hash
    assert computed_hash == "5fa69e4cf90a8bcfab0b4bd0aa0d6374aec88baf70ab7e46d158885ef674a91c"


def test_oliktok_adapter_does_not_mutate_source(primary_nc_path: Path):
    mtime_before = primary_nc_path.stat().st_mtime
    hash_before = hashlib.sha256(primary_nc_path.read_bytes()).hexdigest()

    ds = OliktokAdapter.load(primary_nc_path)
    _ = ds.to_das_dataset()

    mtime_after = primary_nc_path.stat().st_mtime
    hash_after = hashlib.sha256(primary_nc_path.read_bytes()).hexdigest()

    assert mtime_before == mtime_after
    assert hash_before == hash_after


def test_oliktok_real_evaluation_execution(primary_nc_path: Path):
    res = evaluate_oliktok_dataset(primary_nc_path)
    assert res["status"] == "EXECUTED"
    assert res["sample_count"] == 215
    assert res["channel_count"] == 183
    assert res["signal_statistics"]["nan_count"] == 0
    assert res["signal_statistics"]["inf_count"] == 0

    # Strict scientific boundary assertions:
    assert res["assumptions_and_limitations"]["vessel_ground_truth"] is False
    assert res["assumptions_and_limitations"]["ais_available"] is False
    assert res["assumptions_and_limitations"]["causal_damage_ground_truth"] is False
    assert "accuracy" not in res["physical_detector_evaluation"]
    assert "f1" not in res["physical_detector_evaluation"]

    # False critical alarms under ambient wave conditions must be exactly 0
    assert res["physical_detector_evaluation"]["false_critical_escalation_rate_t2_t3"] == 0.0
    assert res["physical_detector_evaluation"]["decision_distribution"]["T2"] == 0
    assert res["physical_detector_evaluation"]["decision_distribution"]["T3"] == 0
    assert res["physical_detector_evaluation"]["decision_distribution"]["TX"] == 0
