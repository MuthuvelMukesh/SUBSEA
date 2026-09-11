from __future__ import annotations

from typing import Iterable

import numpy as np


def classification_metrics(truth: Iterable[str], prediction: Iterable[str]) -> dict[str, object]:
    actual = list(truth)
    predicted = list(prediction)
    if len(actual) != len(predicted) or not actual:
        raise ValueError("truth and prediction must be non-empty and equal length")
    labels = sorted(set(actual) | set(predicted))
    correct = sum(left == right for left, right in zip(actual, predicted))
    per_class: dict[str, dict[str, float | int]] = {}
    for label in labels:
        true_positive = sum(a == label and p == label for a, p in zip(actual, predicted))
        false_positive = sum(a != label and p == label for a, p in zip(actual, predicted))
        false_negative = sum(a == label and p != label for a, p in zip(actual, predicted))
        support = sum(a == label for a in actual)
        precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
        recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = {"precision": precision, "recall": recall, "f1": f1, "support": support}
    macro_precision = float(np.mean([item["precision"] for item in per_class.values()]))
    macro_recall = float(np.mean([item["recall"] for item in per_class.values()]))
    macro_f1 = float(np.mean([item["f1"] for item in per_class.values()]))
    return {"accuracy": correct / len(actual), "labels": labels, "confusion_matrix": [[sum(a == label_a and p == label_p for a, p in zip(actual, predicted)) for label_p in labels] for label_a in labels], "per_class": per_class, "macro_precision": macro_precision, "macro_recall": macro_recall, "macro_f1": macro_f1, "status": "EXECUTED"}


def brier_score(labels: Iterable[int], probabilities: Iterable[float]) -> float:
    actual = np.asarray(list(labels), dtype=float)
    confidence = np.asarray(list(probabilities), dtype=float)
    if actual.size == 0 or actual.size != confidence.size:
        raise ValueError("labels and probabilities must be non-empty and equal length")
    if not np.all(np.isin(actual, (0, 1))) or not np.all(np.isfinite(confidence)) or np.any((confidence < 0) | (confidence > 1)):
        raise ValueError("binary labels and probabilities in [0, 1] are required")
    return float(np.mean((confidence - actual) ** 2))


def calibration_curve(labels: Iterable[int], probabilities: Iterable[float], bins: int = 10) -> list[dict[str, float | int]]:
    actual = np.asarray(list(labels), dtype=float)
    confidence = np.asarray(list(probabilities), dtype=float)
    if not isinstance(bins, int) or isinstance(bins, bool) or bins <= 0 or actual.size == 0 or actual.size != confidence.size:
        raise ValueError("positive bins and non-empty equal-length inputs are required")
    if not np.all(np.isin(actual, (0, 1))) or not np.all(np.isfinite(confidence)) or np.any((confidence < 0) | (confidence > 1)):
        raise ValueError("binary labels and probabilities in [0, 1] are required")
    edges = np.linspace(0, 1, bins + 1)
    curve: list[dict[str, float | int]] = []
    for index, (lower, upper) in enumerate(zip(edges[:-1], edges[1:])):
        mask = (confidence >= lower) & (confidence <= upper if index == bins - 1 else confidence < upper)
        count = int(np.sum(mask))
        curve.append({"lower": float(lower), "upper": float(upper), "count": count, "mean_confidence": float(np.mean(confidence[mask])) if count else 0.0, "empirical_rate": float(np.mean(actual[mask])) if count else 0.0})
    return curve


def bootstrap_confidence_interval(values: Iterable[float], *, statistic: str = "mean", resamples: int = 1000, seed: int = 42) -> dict[str, object]:
    observations = np.asarray(list(values), dtype=float)
    if not np.all(np.isfinite(observations)) or not isinstance(resamples, int) or isinstance(resamples, bool) or resamples <= 0:
        raise ValueError("finite observations and positive resamples are required")
    if statistic != "mean":
        raise ValueError("only mean bootstrap intervals are currently supported")
    if observations.size < 2:
        return pending_result("at least two observations are required")
    rng = np.random.default_rng(seed)
    samples = rng.choice(observations, size=(resamples, observations.size), replace=True)
    estimates = np.mean(samples, axis=1)
    return {"status": "EXECUTED", "estimate": float(np.mean(observations)), "lower": float(np.percentile(estimates, 2.5)), "upper": float(np.percentile(estimates, 97.5)), "observations": int(observations.size), "resamples": resamples, "seed": seed, "reason": None}


def expected_calibration_error(labels: Iterable[int], probabilities: Iterable[float], bins: int = 10) -> float:
    actual = np.asarray(list(labels), dtype=float)
    confidence = np.asarray(list(probabilities), dtype=float)
    if not isinstance(bins, int) or isinstance(bins, bool) or bins <= 0 or actual.size == 0 or actual.size != confidence.size:
        raise ValueError("positive bins and non-empty equal-length inputs are required")
    if not np.all(np.isin(actual, (0, 1))) or not np.all(np.isfinite(confidence)) or np.any((confidence < 0) | (confidence > 1)):
        raise ValueError("binary labels and probabilities in [0, 1] are required")
    edges = np.linspace(0, 1, bins + 1)
    error = 0.0
    for lower, upper in zip(edges[:-1], edges[1:]):
        mask = (confidence >= lower) & (confidence <= upper if upper == 1 else confidence < upper)
        if np.any(mask):
            error += np.mean(mask) * abs(float(np.mean(confidence[mask])) - float(np.mean(actual[mask])))
    return float(error)


def pending_result(reason: str) -> dict[str, object]:
    return {"status": "NOT EXECUTED", "value": None, "reason": reason}


def _cohort_rate(predictions: Iterable[str], cohort: Iterable[bool], predicate: object) -> float:
    decisions = list(predictions)
    members = list(cohort)
    if not decisions or len(decisions) != len(members):
        raise ValueError("predictions and cohort must be non-empty and equal length")
    selected = [decision for decision, included in zip(decisions, members) if included]
    if not selected:
        raise ValueError("cohort must contain at least one trial")
    return float(sum(predicate(decision) for decision in selected) / len(selected))


def adversarial_error_rate(predictions: Iterable[str], adversarial_h1: Iterable[bool]) -> float:
    """Fraction of true adversarial H1 trials incorrectly decided as T0."""

    return _cohort_rate(predictions, adversarial_h1, lambda decision: decision == "T0")


def false_high_escalation_rate(predictions: Iterable[str], benign: Iterable[bool]) -> float:
    """Fraction of benign/non-vessel trials incorrectly decided as T2 or T3."""

    return _cohort_rate(predictions, benign, lambda decision: decision in {"T2", "T3"})
