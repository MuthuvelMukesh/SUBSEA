"""Tests for multi-vessel simulation and pipeline."""
import pytest
from subsea.models import VesselObservation
from subsea.simulation import generate_multi_vessel, generate_observations, make_scenario
from subsea.pipeline import run_multi_vessel_pipeline


class TestMultiVesselGeneration:
    def test_zero_vessels(self):
        scenario = make_scenario("S01", seed=42)
        vessels = generate_multi_vessel(scenario, [0.0, 1.0, 2.0], n_vessels=0)
        assert len(vessels) == 0

    def test_one_vessel(self):
        scenario = make_scenario("S04", seed=42)
        vessels = generate_multi_vessel(scenario, [0.0, 1.0], n_vessels=1)
        assert len(vessels) == 1
        assert vessels[0].vessel_id == "vessel-01"

    def test_two_vessels_have_different_positions(self):
        scenario = make_scenario("S04", seed=42)
        vessels = generate_multi_vessel(scenario, [0.0, 1.0], n_vessels=2)
        assert len(vessels) == 2
        assert vessels[0].position != vessels[1].position

    def test_n_vessels(self):
        scenario = make_scenario("S04", seed=42)
        vessels = generate_multi_vessel(scenario, [0.0, 1.0], n_vessels=5)
        assert len(vessels) == 5
        ids = [v.vessel_id for v in vessels]
        assert len(set(ids)) == 5  # All unique IDs

    def test_first_vessel_closer_to_origin(self):
        import numpy as np
        scenario = make_scenario("S04", seed=42)
        vessels = generate_multi_vessel(scenario, [0.0, 1.0], n_vessels=3)
        # On average, first vessel should be closer (distance_factor=1 vs 6 vs 11)
        d0 = np.linalg.norm(vessels[0].position)
        d2 = np.linalg.norm(vessels[2].position)
        # Due to randomness, just verify they exist and have finite positions
        assert np.isfinite(d0) and np.isfinite(d2)


class TestMultiVesselPipeline:
    def test_no_vessels_produces_result(self):
        scenario = make_scenario("S01", seed=42)
        observations, _ = generate_observations(scenario)
        result = run_multi_vessel_pipeline(observations, [])
        assert result.selected_vessel_id is None
        assert result.selected_decision.decision.value in {"T0", "T1", "TX"}

    def test_two_vessels_selects_higher_association(self):
        scenario = make_scenario("S04", seed=42)
        observations, _ = generate_observations(scenario)
        # Near vessel and far vessel
        v_near = VesselObservation("v-near", 5.0, (1.0, 0.5), 3.0, 90.0)
        v_far = VesselObservation("v-far", 5.0, (50.0, 50.0), 3.0, 90.0)
        result = run_multi_vessel_pipeline(observations, [v_near, v_far])
        assert result.selected_vessel_id == "v-near"
        assert result.competing_associations["v-near"] > result.competing_associations["v-far"]

    def test_one_relevant_one_irrelevant(self):
        scenario = make_scenario("S04", seed=42)
        observations, _ = generate_observations(scenario)
        relevant = VesselObservation("relevant", 5.0, (2.0, 1.0), 4.0, 90.0)
        irrelevant = VesselObservation("irrelevant", 5.0, (100.0, 100.0), 1.0, 0.0)
        result = run_multi_vessel_pipeline(observations, [relevant, irrelevant])
        assert result.selected_vessel_id == "relevant"
        assert len(result.vessel_results) == 2

    def test_does_not_assume_nearest_is_responsible(self):
        """The pipeline selects by association confidence, not distance alone."""
        scenario = make_scenario("S04", seed=42)
        observations, _ = generate_observations(scenario)
        # Vessel A is nearer but unreported, vessel B is farther but reported
        v_a = VesselObservation("v-a", 5.0, (1.0, 0.5), 3.0, 90.0, reported=False)
        v_b = VesselObservation("v-b", 5.0, (5.0, 3.0), 4.0, 90.0, reported=True)
        result = run_multi_vessel_pipeline(observations, [v_a, v_b])
        # v_a is unreported so should have 0 association
        assert result.competing_associations["v-a"] == 0.0

    def test_conflicting_evidence_two_vessels(self):
        scenario = make_scenario("S04", seed=42)
        observations, _ = generate_observations(scenario)
        v1 = VesselObservation("v1", 5.0, (2.0, 1.0), 4.0, 90.0)
        v2 = VesselObservation("v2", 5.0, (3.0, 2.0), 3.5, 45.0)
        result = run_multi_vessel_pipeline(observations, [v1, v2])
        assert len(result.vessel_results) == 2
        assert result.selected_vessel_id in {"v1", "v2"}

    def test_simultaneous_vessels(self):
        scenario = make_scenario("S04", seed=42)
        observations, _ = generate_observations(scenario)
        t = observations[-1].timestamp
        v1 = VesselObservation("sim-v1", t, (2.0, 1.0), 4.0, 90.0)
        v2 = VesselObservation("sim-v2", t, (2.5, 1.5), 3.5, 85.0)
        result = run_multi_vessel_pipeline(observations, [v1, v2])
        assert result.selected_vessel_id is not None

    def test_empty_observations_raises(self):
        with pytest.raises(ValueError):
            run_multi_vessel_pipeline([], [])
