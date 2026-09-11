import numpy as np
import json

from subsea.experiments import run_trials
from subsea.simulation import generate_observations, generate_vessels, make_scenario


def test_all_scenarios_have_explicit_reproducible_definitions():
    for index in range(1, 23):
        scenario_id = f"S{index:02d}"
        scenario = make_scenario(scenario_id, seed=100 + index)
        observations, vessel = generate_observations(scenario)
        observations_again, vessel_again = generate_observations(scenario)
        assert scenario.scenario_id == scenario_id
        assert observations == observations_again
        assert vessel == vessel_again
        assert scenario.description


def test_communication_failure_removes_packets():
    scenario = make_scenario("S08", seed=1)
    observations, _ = generate_observations(scenario)
    assert not any(observation.packet_received for observation in observations)


def test_condition_flags_change_generated_evidence():
    conflict, _ = generate_observations(make_scenario("S13", seed=1))
    counter, vessel = generate_observations(make_scenario("S14", seed=1))
    uncertain, _ = generate_observations(make_scenario("S15", seed=1))
    assert conflict != generate_observations(make_scenario("S04", seed=1))[0]
    assert vessel is not None and vessel.position == (25.0, 25.0)
    assert sum(not observation.packet_received for observation in uncertain) > 0


def test_s22_generates_two_vessels():
    vessels = generate_vessels(make_scenario("S22", seed=1), np.array([0.0, 1.0]))
    assert [vessel.vessel_id for vessel in vessels] == ["vessel-01", "vessel-02"]


def test_s22_trial_manifest_evaluates_all_vessels(tmp_path):
    manifest = json.loads(run_trials("S22", 1, 1, tmp_path / "s22").read_text())
    assert manifest["predictions"][0]["vessel_count"] == 2
    assert manifest["predictions"][0]["vessel_ids"] == ["vessel-01", "vessel-02"]
