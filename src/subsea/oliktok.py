from __future__ import annotations

import datetime
import hashlib
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .das import DasDataset
from .real_data import DataProvenance


@dataclass(frozen=True)
class OliktokDataset:
    file_path: str
    file_name: str
    sha256: str
    format: str
    temporal_samples: int
    channel_count: int
    frequency_bins: int
    frequencies: tuple[float, ...]
    timestamps_iso: tuple[str, ...]
    timestamps_unix: tuple[float, ...]
    sampling_interval_hours: float
    duration_seconds: float
    channel_ids: tuple[int, ...]
    distances_km: tuple[float, ...]
    depths_m: tuple[float, ...]
    burial_depths_m: tuple[float, ...]
    # 2D summary: [time, channel] integrated RMS
    integrated_channel_rms: tuple[tuple[float, ...], ...]
    has_wave_reference: bool
    wave_height_mean: float | None
    wave_period_mean: float | None
    provenance: DataProvenance
    scientific_role: str = "environmental / real DAS robustness validation"

    def to_das_dataset(self) -> DasDataset:
        """Convert integrated channel RMS to standard DasDataset representation."""
        return DasDataset(
            samples=self.integrated_channel_rms,
            timestamps=self.timestamps_unix,
            vessel_distances=None,  # Strictly None: no vessel/AIS ground truth
            channel_count=self.channel_count,
            provenance=self.provenance,
        )


class OliktokAdapter:
    """Read-only adapter for the Dryad Oliktok submarine DAS NetCDF-4 datasets."""

    BASE_TIMESTAMP_ISO = "2023-08-24T04:00:00+00:00"

    @classmethod
    def load(
        cls,
        path: str | Path,
        *,
        verify_sha256: bool = True,
    ) -> OliktokDataset:
        source = Path(path)
        if not source.is_file():
            raise FileNotFoundError(f"Oliktok dataset not found: {source}")

        if source.suffix.lower() != ".nc":
            raise ValueError(f"Oliktok adapter requires a .nc NetCDF file, got: {source.suffix}")

        try:
            import h5py
        except ImportError as error:
            raise RuntimeError("Oliktok NetCDF-4 support requires h5py") from error

        # Calculate SHA-256
        data_bytes = source.read_bytes()
        digest = hashlib.sha256(data_bytes).hexdigest()

        # Base epoch
        base_dt = datetime.datetime.fromisoformat(cls.BASE_TIMESTAMP_ISO)

        # Open in strictly read-only mode
        with h5py.File(source, "r") as h5:
            keys = set(h5.keys())

            # Validate time
            if "time" not in keys:
                raise KeyError("Dataset missing 'time' variable")
            time_arr = h5["time"][:]
            if not np.all(np.isfinite(time_arr)):
                raise ValueError("Time values must be finite")
            if any(r < l for l, r in zip(time_arr[:-1], time_arr[1:])):
                raise ValueError("Timestamps must be non-decreasing")

            time_unit = h5["time"].attrs.get("units", b"").decode("utf-8", errors="ignore")
            is_half_hourly = "minutes" in time_unit.lower() or "half" in source.name.lower()
            interval_hours = 0.5 if is_half_hourly else 1.0

            timestamps_unix = []
            timestamps_iso = []
            for t_val in time_arr:
                if is_half_hourly:
                    dt = base_dt + datetime.timedelta(minutes=float(t_val))
                else:
                    dt = base_dt + datetime.timedelta(hours=float(t_val))
                timestamps_unix.append(dt.timestamp())
                timestamps_iso.append(dt.isoformat())

            duration_seconds = timestamps_unix[-1] - timestamps_unix[0] if len(timestamps_unix) > 1 else 0.0

            # Frequency
            if "frequency" in keys:
                freq_arr = h5["frequency"][:]
                frequencies = tuple(float(f) for f in freq_arr)
            else:
                frequencies = tuple()

            # Channels / Spatial
            if "ch" in keys:
                channel_ids = tuple(int(c) for c in h5["ch"][:])
            elif "site" in keys:
                channel_ids = tuple(int(c) for c in h5["site"][:])
            else:
                channel_ids = tuple(range(h5["strain_spectral_density"].shape[1]))

            num_channels = len(channel_ids)
            num_times = len(time_arr)

            # Distances
            if "dist" in keys:
                dist_arr = h5["dist"][:]
                if dist_arr.ndim == 2:
                    dist_mean = np.nanmean(dist_arr, axis=0)
                    distances_km = tuple(float(d) for d in dist_mean)
                else:
                    distances_km = tuple(float(d) for d in dist_arr)
            else:
                distances_km = tuple(0.0 for _ in range(num_channels))

            # Depths
            if "depth" in keys:
                depth_arr = h5["depth"][:]
                if depth_arr.ndim == 2:
                    depth_mean = np.nanmean(depth_arr, axis=0)
                    depths_m = tuple(float(d) for d in depth_mean)
                else:
                    depths_m = tuple(float(d) for d in depth_arr)
            else:
                depths_m = tuple(0.0 for _ in range(num_channels))

            # Burial depth
            if "burial_depth" in keys:
                b_arr = h5["burial_depth"][:]
                if b_arr.ndim == 2:
                    b_mean = np.nanmean(b_arr, axis=0)
                    burial_depths_m = tuple(float(d) for d in b_mean)
                else:
                    burial_depths_m = tuple(float(d) for d in b_arr)
            else:
                burial_depths_m = tuple(0.0 for _ in range(num_channels))

            # Strain spectral density: integrated RMS
            # Can be 3D (time, channel, frequency) or 4D (time, channel, freq, wavenumber)
            if "strain_spectral_density" in keys:
                ssd = h5["strain_spectral_density"][:]
                if np.isnan(ssd).any() or np.isinf(ssd).any():
                    raise ValueError("strain_spectral_density contains NaN or Inf values")
                # Integrate across frequency bins to obtain band-limited variance -> RMS
                # sqrt(sum(PSD * df)) or sqrt(mean(PSD))
                # For standardized comparability, compute sqrt of mean PSD per window & channel
                integrated_rms = np.sqrt(np.mean(ssd, axis=-1))
            elif "strain_fk_spectral_density" in keys:
                sfk = h5["strain_fk_spectral_density"][:]
                if np.isnan(sfk).any() or np.isinf(sfk).any():
                    raise ValueError("strain_fk_spectral_density contains NaN or Inf values")
                integrated_rms = np.sqrt(np.mean(sfk, axis=(-2, -1)))
            else:
                raise KeyError("No strain spectral density found in dataset")

            # Validate integrated RMS
            if integrated_rms.shape != (num_times, num_channels):
                raise ValueError(f"Unexpected integrated RMS shape: {integrated_rms.shape}, expected ({num_times}, {num_channels})")

            rms_tuple = tuple(tuple(float(v) for v in row) for row in integrated_rms)

            # Oceanographic wave reference metrics (if available)
            has_wave = "target_significant_wave_height" in keys
            wave_h_mean = float(np.mean(h5["target_significant_wave_height"][:])) if has_wave else None
            wave_p_mean = float(np.mean(h5["target_energy_period"][:])) if "target_energy_period" in keys else None

        provenance = DataProvenance(
            path=str(source),
            format="NetCDF-4 / HDF5",
            sha256=digest,
            rows=num_times,
            causal_ground_truth=False,
            status="EXECUTED",
        )

        return OliktokDataset(
            file_path=str(source),
            file_name=source.name,
            sha256=digest,
            format="NetCDF-4 / HDF5",
            temporal_samples=num_times,
            channel_count=num_channels,
            frequency_bins=len(frequencies),
            frequencies=frequencies,
            timestamps_iso=tuple(timestamps_iso),
            timestamps_unix=tuple(timestamps_unix),
            sampling_interval_hours=interval_hours,
            duration_seconds=duration_seconds,
            channel_ids=channel_ids,
            distances_km=distances_km,
            depths_m=depths_m,
            burial_depths_m=burial_depths_m,
            integrated_channel_rms=rms_tuple,
            has_wave_reference=has_wave,
            wave_height_mean=wave_h_mean,
            wave_period_mean=wave_p_mean,
            provenance=provenance,
        )


def load_oliktok_dataset(path: str | Path | None = None) -> OliktokDataset:
    """Convenience loader for the primary Oliktok mooring hourly dataset."""
    if path is None:
        path = Path("data/Dryad_Oliktok/oliktok_das_mooring_hourly_dataset.nc")
    return OliktokAdapter.load(path)
