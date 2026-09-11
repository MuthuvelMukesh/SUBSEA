import numpy as np

from subsea.association import spatial_association, temporal_association
from subsea.features import acceleration_magnitude, physical_confidence, spectral_features
from subsea.metrics import expected_calibration_error
from subsea.pipeline import run_pipeline
from subsea.simulation import generate_observations, make_scenario


def test_acceleration_magnitude_and_spectral_features():
    samples = np.tile([1.0, 0.0, 0.0], (64, 1))
    assert np.allclose(acceleration_magnitude(samples), 1.0)
    features = spectral_features(samples, 50.0)
    assert features["rms"] == 1.0
    assert physical_confidence(features, baseline_rms=0.5, disturbance_rms=1.5) == 0.5


def test_association_is_bounded_and_decreases():
    assert spatial_association(0, 10) == 1
    assert spatial_association(20, 10) == 0
    assert temporal_association(0, 5) == 1
    assert temporal_association(10, 5) == 0


def test_seeded_end_to_end_scenario_is_reproducible():
    scenario = make_scenario("S04", seed=7)
    observations, vessel = generate_observations(scenario)
    first = run_pipeline(observations, vessel)
    observations_again, vessel_again = generate_observations(scenario)
    second = run_pipeline(observations_again, vessel_again)
    assert first == second
    assert first.decision.value in {"T0", "T1", "T2", "T3", "TX"}
    assert first.audit["health"]["health"] <= 1.0


def test_missing_corroboration_is_auditable():
    scenario = make_scenario("S18", seed=7)
    observations, vessel = generate_observations(scenario)
    result = run_pipeline(observations, vessel)
    assert "reported vessel corroboration" in result.missing_corroboration
    assert "no AIS-like corroboration" in result.counter_evidence


def test_stale_sensor_fails_closed_to_tx():
    from subsea.models import SensorObservation

    result = run_pipeline([SensorObservation("n", 0.0, (1.0, 0.0, 0.0), (0.0, 0.0))], None, now=10.0, packet_timeout=1.0)
    assert result.decision.value == "TX"


def test_calibration_metric_is_bounded():
    value = expected_calibration_error([1, 0, 1, 1], [0.9, 0.1, 0.8, 0.4])
    assert 0 <= value <= 1
