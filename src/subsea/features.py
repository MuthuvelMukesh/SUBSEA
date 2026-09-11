from __future__ import annotations

import math
from typing import Iterable

import numpy as np


def acceleration_magnitude(samples: Iterable[Iterable[float]]) -> np.ndarray:
    values = np.asarray(list(samples), dtype=float)
    if values.ndim != 2 or values.shape[1] < 3:
        raise ValueError("samples must contain at least three acceleration axes")
    return np.linalg.norm(values[:, :3], axis=1)


def spectral_features(samples: Iterable[Iterable[float]], sampling_rate: float) -> dict[str, float]:
    magnitude = acceleration_magnitude(samples)
    if sampling_rate <= 0 or magnitude.size == 0:
        raise ValueError("sampling_rate must be positive and samples must not be empty")
    centered = magnitude - np.mean(magnitude)
    spectrum = np.abs(np.fft.rfft(centered)) ** 2
    frequencies = np.fft.rfftfreq(centered.size, 1.0 / sampling_rate)
    if spectrum.size > 1:
        spectrum[0] = 0.0
    total = float(np.sum(spectrum))
    probabilities = spectrum / total if total > 0 else np.zeros_like(spectrum)
    entropy = float(-np.sum(probabilities[probabilities > 0] * np.log2(probabilities[probabilities > 0])))
    dominant = float(frequencies[int(np.argmax(spectrum))]) if total > 0 else 0.0
    return {
        "mean": float(np.mean(magnitude)),
        "rms": float(np.sqrt(np.mean(magnitude**2))),
        "variance": float(np.var(magnitude)),
        "std": float(np.std(magnitude)),
        "peak": float(np.max(magnitude)),
        "peak_to_rms": float(np.max(magnitude) / max(np.sqrt(np.mean(magnitude**2)), 1e-12)),
        "spectral_energy": total,
        "dominant_frequency": dominant,
        "spectral_entropy": entropy,
    }


def physical_confidence(features: dict[str, float], *, baseline_rms: float, disturbance_rms: float) -> float:
    if disturbance_rms <= baseline_rms:
        raise ValueError("disturbance_rms must exceed baseline_rms")
    confidence = (features["rms"] - baseline_rms) / (disturbance_rms - baseline_rms)
    return float(np.clip(confidence, 0.0, 1.0))
