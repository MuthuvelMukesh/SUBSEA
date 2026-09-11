import pytest

from subsea.geometry import distance_to_polyline, nearest_point_on_polyline
from subsea.models import SensorObservation, VesselObservation
from subsea.pipeline import run_pipeline
from subsea.trajectory import closest_point_of_approach, crossing_detected, dwell_time


def test_nearest_point_and_distance_use_polyline_segments():
    cable = ((0.0, 0.0), (10.0, 0.0), (10.0, 10.0))
    point, distance = nearest_point_on_polyline((6.0, 3.0), cable)
    assert point == pytest.approx((6.0, 0.0))
    assert distance == pytest.approx(3.0)
    assert distance_to_polyline((6.0, 3.0), cable) == pytest.approx(3.0)


def test_trajectory_metrics_are_explicit():
    trajectory = ((0.0, 2.0), (1.0, 0.5), (2.0, -0.5), (3.0, -2.0))
    timestamps = (0.0, 1.0, 2.0, 3.0)
    assert closest_point_of_approach(trajectory, ((0.0, 0.0), (3.0, 0.0)))[0] == pytest.approx(0.5)
    assert dwell_time(trajectory, timestamps, ((0.0, 0.0), (3.0, 0.0)), radius=1.0) == pytest.approx(2.0)
    assert crossing_detected(trajectory, ((0.0, 0.0), (3.0, 0.0))) is True
    assert crossing_detected(((8.0, -1.0), (8.0, 1.0)), ((0.0, 0.0), (10.0, 0.0), (10.0, 10.0))) is True


def test_pipeline_can_use_explicit_cable_geometry():
    observations = [SensorObservation("n", 0.0, (1.0, 0.0, 0.0), (0.0, 0.0))]
    vessel = VesselObservation("v", 0.0, (6.0, 3.0), 4.0, 90.0)
    result = run_pipeline(observations, vessel, cable_geometry=((0.0, 0.0), (10.0, 0.0), (10.0, 10.0)))
    assert result.audit["features"]
    assert result.audit["cable_geometry"] == ((0.0, 0.0), (10.0, 0.0), (10.0, 10.0))


def test_malformed_geometry_is_rejected():
    with pytest.raises(ValueError):
        nearest_point_on_polyline((0.0, 0.0), ((0.0, 0.0),))
    with pytest.raises(ValueError):
        crossing_detected(((0.0, 0.0), (1.0, 1.0)), ((0.0, 0.0),))
    with pytest.raises(ValueError):
        nearest_point_on_polyline((0.0,), ((0.0, 0.0), (1.0, 1.0)))
    with pytest.raises(ValueError):
        crossing_detected(((float("nan"), 0.0),), ((0.0, 0.0), (1.0, 1.0)))
    with pytest.raises(ValueError):
        crossing_detected((("bad", 0.0), (1.0, 1.0)), ((0.0, 0.0), (1.0, 1.0)))


def test_dwell_rejects_non_finite_inputs():
    with pytest.raises(ValueError):
        dwell_time(((0.0, 1.0), (1.0, 1.0)), (0.0, float("nan")), ((0.0, 0.0), (1.0, 0.0)), radius=1.0)
