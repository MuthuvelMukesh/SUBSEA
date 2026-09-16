from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DataProvenance:
    path: str
    format: str
    sha256: str
    rows: int
    causal_ground_truth: bool = False
    status: str = "EXECUTED"


@dataclass(frozen=True)
class LoadedDataset:
    records: tuple[dict[str, Any], ...]
    provenance: DataProvenance


def _normalize_timestamp(value: Any) -> Any:
    if isinstance(value, bool):
        raise ValueError("timestamp must be finite and non-boolean")
    if isinstance(value, (int, float)):
        if not math.isfinite(float(value)):
            raise ValueError("timestamp must be finite")
        return float(value)
    if not isinstance(value, str):
        raise ValueError("unsupported timestamp type")
    try:
        numeric = float(value)
        if not math.isfinite(numeric):
            raise ValueError("timestamp must be finite")
        return numeric
    except ValueError as error:
        if str(error) == "timestamp must be finite":
            raise
        try:
            normalized = value.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(normalized)
        except ValueError as error:
            raise ValueError(f"unsupported timestamp value: {value}") from error
        if parsed.tzinfo is None:
            raise ValueError("timestamp must include an explicit timezone")
        return parsed.timestamp()


def _normalize_records(records: list[dict[str, Any]], timestamp_column: str | None) -> tuple[dict[str, Any], ...]:
    normalized: list[dict[str, Any]] = []
    for record in records:
        copied = dict(record)
        if timestamp_column and timestamp_column in copied:
            copied[timestamp_column] = _normalize_timestamp(copied[timestamp_column])
        normalized.append(copied)
    return tuple(normalized)


def _read_csv(path: Path, timestamp_column: str | None) -> tuple[dict[str, Any], ...]:
    with path.open(newline="", encoding="utf-8") as handle:
        return _normalize_records(list(csv.DictReader(handle)), timestamp_column)


def _read_json(path: Path, timestamp_column: str | None) -> tuple[dict[str, Any], ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = payload.get("records") if isinstance(payload, dict) else payload
    if not isinstance(records, list) or not all(isinstance(record, dict) for record in records):
        raise ValueError("JSON input must contain a list of record objects")
    return _normalize_records(records, timestamp_column)


def _read_hdf5(path: Path, dataset_name: str | None, timestamp_column: str | None) -> tuple[dict[str, Any], ...]:
    if not dataset_name:
        raise ValueError("hdf5_dataset is required for HDF5 input")
    try:
        import h5py
    except ImportError as error:
        raise RuntimeError("HDF5 support requires h5py") from error
    with h5py.File(path, "r") as handle:
        if dataset_name not in handle:
            raise KeyError(f"HDF5 dataset not found: {dataset_name}")
        values = handle[dataset_name][()]
    rows = values.tolist()
    if not isinstance(rows, list):
        rows = [rows]
    records = [{"value": row if isinstance(row, list) else [row]} for row in rows]
    return _normalize_records(records, timestamp_column)


def _read_numpy(path: Path, timestamp_column: str | None) -> tuple[dict[str, Any], ...]:
    import numpy as np
    values = np.load(path)
    rows = values.tolist()
    if not isinstance(rows, list):
        rows = [rows]
    records = [{"value": row if isinstance(row, list) else [row]} for row in rows]
    return _normalize_records(records, timestamp_column)


def load_dataset(path: str | Path, *, timestamp_column: str | None = "timestamp", hdf5_dataset: str | None = None) -> LoadedDataset:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(source)
    suffix = source.suffix.lower()
    formats = {".csv": "csv", ".json": "json", ".h5": "hdf5", ".hdf5": "hdf5", ".npy": "numpy"}
    if suffix not in formats:
        raise ValueError(f"unsupported data format: {suffix or 'unknown'}")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    data_format = formats[suffix]
    if data_format == "csv":
        records = _read_csv(source, timestamp_column)
    elif data_format == "json":
        records = _read_json(source, timestamp_column)
    elif data_format == "numpy":
        records = _read_numpy(source, timestamp_column)
    else:
        records = _read_hdf5(source, hdf5_dataset, timestamp_column)
    provenance = DataProvenance(str(source), data_format, digest, len(records))
    return LoadedDataset(records, provenance)

