import hashlib
import json

import pytest

from subsea.real_data import load_dataset


def test_csv_loader_normalizes_timestamps_and_preserves_raw(tmp_path):
    path = tmp_path / "ais.csv"
    path.write_text("timestamp,vessel_id,lat\n2026-01-01T00:00:00Z,v1,1.5\n", encoding="utf-8")
    before = hashlib.sha256(path.read_bytes()).hexdigest()

    dataset = load_dataset(path, timestamp_column="timestamp")

    assert dataset.records[0]["timestamp"] == 1767225600.0
    assert dataset.records[0]["vessel_id"] == "v1"
    assert dataset.provenance.format == "csv"
    assert dataset.provenance.sha256 == before
    assert dataset.provenance.causal_ground_truth is False
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_json_loader_requires_record_objects(tmp_path):
    path = tmp_path / "data.json"
    path.write_text(json.dumps([{"timestamp": 1, "value": 2}]), encoding="utf-8")
    dataset = load_dataset(path)
    assert dataset.records == ({"timestamp": 1.0, "value": 2},)

    invalid = tmp_path / "invalid.json"
    invalid.write_text(json.dumps([1, 2]), encoding="utf-8")
    with pytest.raises(ValueError, match="record objects"):
        load_dataset(invalid)


def test_unsupported_format_is_rejected(tmp_path):
    path = tmp_path / "data.txt"
    path.write_text("data", encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported data format"):
        load_dataset(path)


def test_naive_timestamp_is_rejected(tmp_path):
    path = tmp_path / "naive.json"
    path.write_text(json.dumps([{"timestamp": "2026-01-01T00:00:00", "value": 1}]), encoding="utf-8")
    with pytest.raises(ValueError, match="timezone"):
        load_dataset(path)


def test_non_finite_timestamp_is_rejected(tmp_path):
    path = tmp_path / "nonfinite.json"
    path.write_text(json.dumps([{"timestamp": "nan", "value": 1}]), encoding="utf-8")
    with pytest.raises(ValueError, match="finite"):
        load_dataset(path)


def test_boolean_timestamp_is_rejected(tmp_path):
    path = tmp_path / "boolean.json"
    path.write_text(json.dumps([{"timestamp": True, "value": 1}]), encoding="utf-8")
    with pytest.raises(ValueError, match="non-boolean"):
        load_dataset(path)


def test_unsupported_timestamp_type_is_rejected(tmp_path):
    path = tmp_path / "object.json"
    path.write_text(json.dumps([{"timestamp": None, "value": 1}]), encoding="utf-8")
    with pytest.raises(ValueError, match="timestamp type"):
        load_dataset(path)


def test_hdf5_loader_reads_named_dataset_without_mutation(tmp_path):
    h5py = pytest.importorskip("h5py")
    path = tmp_path / "das.h5"
    with h5py.File(path, "w") as handle:
        handle.create_dataset("signal", data=[[1.0, 2.0], [3.0, 4.0]])
    before = hashlib.sha256(path.read_bytes()).hexdigest()

    dataset = load_dataset(path, hdf5_dataset="signal")

    assert dataset.records == ({"value": [1.0, 2.0]}, {"value": [3.0, 4.0]})
    assert dataset.provenance.format == "hdf5"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
