from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .real_data import DataProvenance


@dataclass(frozen=True)
class DasSchema:
    signal_path: str
    timestamp_path: str | None = None
    distance_path: str | None = None
    channel_axis: int = 1


@dataclass(frozen=True)
class DasDataset:
    samples: tuple[tuple[float, ...], ...]
    timestamps: tuple[float, ...]
    vessel_distances: tuple[float, ...] | None
    channel_count: int
    provenance: DataProvenance


def _as_rows(values: Any, channel_axis: int) -> tuple[tuple[float, ...], ...]:
    if channel_axis not in {0, 1}:
        raise ValueError("channel_axis must be 0 or 1")
    rows = values.tolist()
    if not isinstance(rows, list):
        rows = [rows]
    if rows and not isinstance(rows[0], list):
        rows = [[row] for row in rows]
    if channel_axis == 0 and rows:
        rows = [list(row) for row in zip(*rows)]
    result = tuple(tuple(float(value) for value in row) for row in rows)
    if any(not math.isfinite(value) for row in result for value in row):
        raise ValueError("DAS signal values must be finite")
    return result


def load_das_hdf5(path: str | Path, schema: DasSchema) -> DasDataset:
    source = Path(path)
    if source.suffix.lower() not in {".h5", ".hdf5"}:
        raise ValueError("DAS adapter requires an HDF5 file")
    if not source.is_file():
        raise FileNotFoundError(source)
    try:
        import h5py
    except ImportError as error:
        raise RuntimeError("DAS HDF5 support requires h5py") from error
    with h5py.File(source, "r") as handle:
        if schema.signal_path not in handle:
            raise KeyError(f"DAS signal dataset not found: {schema.signal_path}")
        samples = _as_rows(handle[schema.signal_path][()], schema.channel_axis)
        timestamps = tuple(value for value in handle[schema.timestamp_path][()]) if schema.timestamp_path else tuple(float(index) for index in range(len(samples)))
        distances = tuple(value for value in handle[schema.distance_path][()]) if schema.distance_path else None
    if any(isinstance(value, bool) for value in timestamps) or distances is not None and any(isinstance(value, bool) for value in distances):
        raise ValueError("DAS timestamps and distances must be numeric")
    timestamps = tuple(float(value) for value in timestamps)
    distances = None if distances is None else tuple(float(value) for value in distances)
    if any(not math.isfinite(value) for value in timestamps) or any(right < left for left, right in zip(timestamps[:-1], timestamps[1:])) or distances is not None and any(not math.isfinite(value) or value < 0 for value in distances):
        raise ValueError("DAS timestamps and distances must be finite")
    if len(timestamps) != len(samples):
        raise ValueError("DAS timestamps must match signal sample count")
    if distances is not None and len(distances) != len(samples):
        raise ValueError("DAS vessel distances must match signal sample count")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    provenance = DataProvenance(str(source), "das_hdf5", digest, len(samples), causal_ground_truth=False)
    return DasDataset(samples, timestamps, distances, len(samples[0]) if samples else 0, provenance)
