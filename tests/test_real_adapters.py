import json

import pytest

from subsea.ais import load_ais_records
from subsea.das import DasSchema, load_das_hdf5


def test_ais_records_are_ordered_without_inventing_identity():
    records = load_ais_records([
        {"timestamp": "2026-01-01T00:00:02Z", "latitude": 2, "longitude": 3, "speed": 4, "heading": 90},
        {"timestamp": "2026-01-01T00:00:01Z", "latitude": 1, "longitude": 2, "speed": 3, "heading": 80, "vessel_id": "v1"},
    ])
    assert [record.timestamp for record in records] == [1767225601.0, 1767225602.0]
    assert records[0].vessel_id == "v1"
    assert records[1].vessel_id is None
    assert records[1].reported is True


def test_ais_interpolation_requires_explicit_opt_in():
    with pytest.raises(ValueError, match="interpolation"):
        load_ais_records([], interpolate=True)


def test_ais_rejects_negative_speed_and_uncertainty():
    with pytest.raises(ValueError, match="non-negative"):
        load_ais_records([{"timestamp": 1, "latitude": 0, "longitude": 0, "speed": -1}])


def test_ais_rejects_invalid_heading_and_reported_type():
    with pytest.raises(ValueError, match="heading"):
        load_ais_records([{"timestamp": 1, "latitude": 0, "longitude": 0, "heading": 360}])
    with pytest.raises(ValueError, match="reported"):
        load_ais_records([{"timestamp": 1, "latitude": 0, "longitude": 0, "reported": "false"}])


def test_das_hdf5_adapter_reads_configured_paths_without_causal_truth(tmp_path):
    h5py = pytest.importorskip("h5py")
    path = tmp_path / "marlinks.h5"
    with h5py.File(path, "w") as handle:
        handle.create_dataset("/das/signal", data=[[1.0, 2.0], [3.0, 4.0]])
        handle.create_dataset("/meta/timestamp", data=[1.0, 2.0])
        handle.create_dataset("/meta/distance", data=[10.0, 20.0])
    dataset = load_das_hdf5(path, DasSchema(signal_path="/das/signal", timestamp_path="/meta/timestamp", distance_path="/meta/distance"))
    assert dataset.samples == ((1.0, 2.0), (3.0, 4.0))
    assert dataset.timestamps == (1.0, 2.0)
    assert dataset.vessel_distances == (10.0, 20.0)
    assert dataset.provenance.causal_ground_truth is False
