import pytest

from subsea.metrics import (
    brier_score,
    bootstrap_confidence_interval,
    calibration_curve,
    classification_metrics,
)


def test_classification_metrics_include_per_class_scores():
    result = classification_metrics(["positive", "positive", "negative"], ["positive", "negative", "negative"])
    assert result["accuracy"] == pytest.approx(2 / 3)
    assert result["per_class"]["positive"]["recall"] == pytest.approx(0.5)
    assert result["macro_f1"] == pytest.approx(2 / 3)


def test_brier_score_is_bounded():
    assert brier_score([1, 0], [0.9, 0.1]) == pytest.approx(0.01)
    with pytest.raises(ValueError):
        brier_score([1], [1.2])


def test_calibration_curve_is_explicit_about_bins():
    curve = calibration_curve([1, 0, 1], [0.9, 0.1, 0.8], bins=2)
    assert sum(point["count"] for point in curve) == 3
    assert all(set(("lower", "upper", "count", "mean_confidence", "empirical_rate")) <= point.keys() for point in curve)


def test_ece_rejects_invalid_binary_inputs():
    from subsea.metrics import expected_calibration_error

    with pytest.raises(ValueError):
        expected_calibration_error([0.5], [0.5])
    with pytest.raises(ValueError):
        expected_calibration_error([0], [1.2])
    with pytest.raises(ValueError):
        expected_calibration_error([0], [0.5], bins=0)
    with pytest.raises(ValueError):
        expected_calibration_error([0], [0.5], bins=2.5)


def test_bootstrap_ci_requires_enough_observations_and_is_seeded():
    assert bootstrap_confidence_interval([0.5], seed=1)["status"] == "NOT EXECUTED"
    with pytest.raises(ValueError):
        bootstrap_confidence_interval([float("nan")])
    with pytest.raises(ValueError):
        bootstrap_confidence_interval([0.0, 1.0], resamples=2.5)
    first = bootstrap_confidence_interval([0.0, 1.0, 1.0, 0.0], resamples=200, seed=4)
    second = bootstrap_confidence_interval([0.0, 1.0, 1.0, 0.0], resamples=200, seed=4)
    assert first == second
    assert first["status"] == "EXECUTED"
    assert first["lower"] <= first["estimate"] <= first["upper"]
