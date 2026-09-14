"""Tests for all S01-S22 scenarios.

Each scenario must be genuinely executable through the complete pipeline
and produce distinguishable conditions.
"""
import pytest
from subsea.simulation import make_scenario, generate_observations, SUPPORTED_SCENARIOS
from subsea.pipeline import run_pipeline


class TestAllScenarios:
    """Every scenario must execute without error and produce a valid decision."""

    @pytest.mark.parametrize("scenario_id", sorted(SUPPORTED_SCENARIOS))
    def test_scenario_executes(self, scenario_id):
        scenario = make_scenario(scenario_id, seed=42)
        observations, vessel = generate_observations(scenario)
        result = run_pipeline(observations, vessel, environmental_event=scenario.environmental_event)
        assert result.decision.value in {"T0", "T1", "T2", "T3", "TX"}
        assert 0 <= result.physical_confidence <= 1
        assert 0 <= result.association_confidence <= 1
        assert 0 <= result.reliability <= 1
        assert 0 <= result.uncertainty <= 1

    @pytest.mark.parametrize("scenario_id", sorted(SUPPORTED_SCENARIOS))
    def test_scenario_is_reproducible(self, scenario_id):
        scenario = make_scenario(scenario_id, seed=7)
        obs1, v1 = generate_observations(scenario)
        r1 = run_pipeline(obs1, v1, environmental_event=scenario.environmental_event)
        obs2, v2 = generate_observations(scenario)
        r2 = run_pipeline(obs2, v2, environmental_event=scenario.environmental_event)
        assert r1.decision == r2.decision
        assert r1.physical_confidence == r2.physical_confidence


class TestScenarioConditions:
    """Verify scenario-specific conditions produce expected evidence behavior."""

    def test_s01_normal_no_disturbance(self):
        scenario = make_scenario("S01", seed=42)
        assert not scenario.vessel_present
        assert not scenario.disturbance_present
        obs, v = generate_observations(scenario)
        result = run_pipeline(obs, v)
        assert result.decision.value in {"T0", "TX"}

    def test_s02_physical_only(self):
        scenario = make_scenario("S02", seed=42)
        assert not scenario.vessel_present
        assert scenario.disturbance_present
        obs, v = generate_observations(scenario)
        result = run_pipeline(obs, v)
        # High physical but no vessel → T1 or T0
        assert result.physical_confidence > 0.3

    def test_s03_vessel_only(self):
        scenario = make_scenario("S03", seed=42)
        assert scenario.vessel_present
        assert not scenario.disturbance_present
        obs, v = generate_observations(scenario)
        result = run_pipeline(obs, v)
        # Vessel present but no physical disturbance → T0
        assert result.decision.value in {"T0", "TX"}

    def test_s04_vessel_plus_disturbance(self):
        scenario = make_scenario("S04", seed=42)
        assert scenario.vessel_present
        assert scenario.disturbance_present
        obs, v = generate_observations(scenario)
        result = run_pipeline(obs, v)
        # Should produce T2 or T3 (vessel + disturbance)
        assert result.decision.value in {"T2", "T3"}

    def test_s05_environmental(self):
        scenario = make_scenario("S05", seed=42)
        assert scenario.environmental_event
        obs, v = generate_observations(scenario)
        result = run_pipeline(obs, v, environmental_event=True)
        # Environmental event produces physical evidence but different hypothesis
        assert result.hypothesis_scores.get("environmental_disturbance", 0) > 0

    def test_s06_mechanical(self):
        scenario = make_scenario("S06", seed=42)
        assert scenario.mechanical_event
        obs, v = generate_observations(scenario)
        result = run_pipeline(obs, v)
        assert result.physical_confidence > 0

    def test_s07_sensor_failure(self):
        scenario = make_scenario("S07", seed=42)
        assert scenario.sensor_failure
        obs, v = generate_observations(scenario)
        result = run_pipeline(obs, v)
        # Sensor failure should degrade health → TX
        assert result.decision.value == "TX"

    def test_s08_communication_failure(self):
        scenario = make_scenario("S08", seed=42)
        assert scenario.communication_failure
        obs, v = generate_observations(scenario)
        result = run_pipeline(obs, v)
        assert result.decision.value == "TX"

    def test_s09_noise_stress(self):
        scenario = make_scenario("S09", seed=42)
        assert scenario.noise_stress
        assert scenario.noise_level > 0.1

    def test_s10_packet_loss(self):
        scenario = make_scenario("S10", seed=42)
        assert scenario.packet_loss > 0
        obs, v = generate_observations(scenario)
        lost = sum(1 for o in obs if not o.packet_received)
        assert lost > 0

    def test_s11_spatial_mismatch(self):
        scenario = make_scenario("S11", seed=42)
        assert scenario.spatial_mismatch
        obs, v = generate_observations(scenario)
        result = run_pipeline(obs, v)
        # Spatial mismatch → low spatial association
        assert result.association_confidence < 0.7

    def test_s12_temporal_mismatch(self):
        scenario = make_scenario("S12", seed=42)
        assert scenario.temporal_mismatch

    def test_s13_conflicting_evidence(self):
        scenario = make_scenario("S13", seed=42)
        assert scenario.conflicting_evidence

    def test_s14_counter_evidence(self):
        scenario = make_scenario("S14", seed=42)
        assert scenario.counter_evidence
        obs, v = generate_observations(scenario)
        result = run_pipeline(obs, v)
        assert len(result.counter_evidence) > 0

    def test_s15_high_uncertainty(self):
        scenario = make_scenario("S15", seed=42)
        assert scenario.high_uncertainty
        assert scenario.packet_loss >= 0.5

    def test_s16_absence_corroboration(self):
        scenario = make_scenario("S16", seed=42)
        assert scenario.absence_corroboration
        obs, v = generate_observations(scenario)
        result = run_pipeline(obs, v)
        assert len(result.missing_corroboration) > 0

    def test_s17_spoofing(self):
        scenario = make_scenario("S17", seed=42)
        assert scenario.spoofing

    def test_s18_transponder_suppression(self):
        scenario = make_scenario("S18", seed=42)
        obs, v = generate_observations(scenario)
        assert v is not None
        assert not v.reported

    def test_s19_timestamp_manipulation(self):
        scenario = make_scenario("S19", seed=42)
        assert scenario.timestamp_manipulation

    def test_s20_spatial_manipulation(self):
        scenario = make_scenario("S20", seed=42)
        assert scenario.spatial_manipulation

    def test_s21_combined_adversarial(self):
        scenario = make_scenario("S21", seed=42)
        assert scenario.spoofing
        assert scenario.timestamp_manipulation
        assert scenario.spatial_manipulation

    def test_s22_multiple_vessels(self):
        scenario = make_scenario("S22", seed=42)
        assert scenario.multiple_targets
        obs, v = generate_observations(scenario)
        from subsea.simulation import generate_vessels
        vessels = generate_vessels(scenario, tuple(o.timestamp for o in obs))
        assert len(vessels) >= 2
