"""Tests for DAS/AIS association pipeline."""
import pytest
from subsea.ais import AisPoint, load_ais_records
from subsea.das_ais_association import (
    DasEvent, associate_das_ais, associate_all_vessels,
    find_nearest_ais, ais_point_to_vessel_observation,
)


class TestAisPointConversion:
    def test_converts_to_vessel_observation(self):
        point = AisPoint(1000.0, 55.0, 3.0, 5.0, 90.0, vessel_id="v1")
        vo = ais_point_to_vessel_observation(point)
        assert vo.vessel_id == "v1"
        assert vo.position == (55.0, 3.0)
        assert vo.speed == 5.0
        assert vo.heading == 90.0

    def test_handles_none_speed_heading(self):
        point = AisPoint(1000.0, 55.0, 3.0, None, None, vessel_id="v1")
        vo = ais_point_to_vessel_observation(point)
        assert vo.speed == 0.0
        assert vo.heading == 0.0


class TestFindNearestAis:
    def test_finds_nearest_in_time(self):
        points = [
            AisPoint(100.0, 55.0, 3.0, 5.0, 90.0, vessel_id="v1"),
            AisPoint(200.0, 55.1, 3.1, 5.0, 90.0, vessel_id="v1"),
            AisPoint(300.0, 55.2, 3.2, 5.0, 90.0, vessel_id="v1"),
        ]
        nearest = find_nearest_ais(195.0, points)
        assert nearest.timestamp == 200.0

    def test_returns_none_beyond_max_offset(self):
        points = [AisPoint(100.0, 55.0, 3.0, 5.0, 90.0)]
        nearest = find_nearest_ais(500.0, points, max_time_offset=100.0)
        assert nearest is None

    def test_empty_points_returns_none(self):
        assert find_nearest_ais(100.0, []) is None


class TestDasAisAssociation:
    def _cable(self):
        return ((0.0, 0.0), (10.0, 0.0))

    def test_no_vessel_in_window(self):
        event = DasEvent(100.0, 5.0, 1.5, {"rms": 1.5})
        result = associate_das_ais(event, [], self._cable())
        assert result.decision == "no_vessel_in_window"
        assert result.vessel_id is None
        assert result.is_causal_claim is False

    def test_strong_association(self):
        event = DasEvent(100.0, 5.0, 1.5, {"rms": 1.5})
        points = [AisPoint(100.0, 1.0, 0.5, 5.0, 90.0, vessel_id="v1")]
        result = associate_das_ais(event, points, self._cable())
        assert result.vessel_id == "v1"
        assert result.is_causal_claim is False
        assert result.association is not None

    def test_weak_association_far_vessel(self):
        event = DasEvent(100.0, 5.0, 1.5, {"rms": 1.5})
        points = [AisPoint(100.0, 50.0, 50.0, 5.0, 90.0, vessel_id="v-far")]
        result = associate_das_ais(event, points, self._cable(),
                                   interaction_radius=10.0)
        assert result.decision in {"no_association", "weak_association"}

    def test_cable_too_short_raises(self):
        event = DasEvent(100.0, 5.0, 1.5, {"rms": 1.5})
        with pytest.raises(ValueError):
            associate_das_ais(event, [], ((0.0, 0.0),))


class TestAssociateAllVessels:
    def test_multiple_vessels_ranked(self):
        cable = ((0.0, 0.0), (10.0, 0.0))
        event = DasEvent(100.0, 5.0, 1.5, {"rms": 1.5})
        points = [
            AisPoint(100.0, 1.0, 0.5, 5.0, 90.0, vessel_id="v-near"),
            AisPoint(100.0, 50.0, 50.0, 2.0, 0.0, vessel_id="v-far"),
        ]
        results = associate_all_vessels(event, points, cable)
        assert len(results) == 2
        # Nearest vessel should be first (highest association)
        assert results[0].vessel_id == "v-near"

    def test_no_vessels(self):
        cable = ((0.0, 0.0), (10.0, 0.0))
        event = DasEvent(100.0, 5.0, 1.5, {"rms": 1.5})
        results = associate_all_vessels(event, [], cable)
        assert len(results) == 1
        assert results[0].decision == "no_vessels_available"


class TestAisDeduplicationAndGaps:
    def test_load_deduplicates_by_sort(self):
        records = [
            {"timestamp": 200.0, "latitude": 55.0, "longitude": 3.0},
            {"timestamp": 100.0, "latitude": 55.1, "longitude": 3.1},
            {"timestamp": 150.0, "latitude": 55.05, "longitude": 3.05},
        ]
        points = load_ais_records(records)
        assert len(points) == 3
        assert points[0].timestamp < points[1].timestamp < points[2].timestamp
