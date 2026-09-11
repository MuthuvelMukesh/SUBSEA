import copy

import pytest

from subsea.baselines import evaluate_method
from subsea.experiments import run_method_comparison
from subsea.models import DecisionState
from subsea.pipeline import run_pipeline
from subsea.simulation import generate_observations, make_scenario


@pytest.fixture
def sample_case():
    scenario = make_scenario("S04", seed=9)
    observations, vessel = generate_observations(scenario)
    return scenario, run_pipeline(observations, vessel)


def test_baselines_return_stable_records(sample_case):
    scenario, result = sample_case
    methods = ["physical_only", "vessel_only", "weighted", "proposed"]
    records = [evaluate_method(method, result, scenario) for method in methods]
    assert {record["method"] for record in records} == set(methods)
    assert all(record["status"] == "EXECUTED" for record in records)
    assert all(record["decision"] in {state.value for state in DecisionState} for record in records)
    assert records[-1]["decision"] == result.decision.value
    assert records[0]["truth"]["vessel_present"] is True


def test_ablation_records_are_pure_and_auditable(sample_case):
    scenario, result = sample_case
    original = copy.deepcopy(result)
    record = evaluate_method("without_uncertainty", result, scenario)
    assert record["changed_components"] == ("uncertainty",)
    assert record["inputs"]["uncertainty"] == result.uncertainty
    assert result == original


@pytest.mark.parametrize(
    ("method", "component"),
    [
        ("without_health", "health"),
        ("without_counter_evidence", "counter_evidence"),
        ("without_spatial_temporal_association", "spatial_temporal_association"),
        ("without_behaviour", "behaviour"),
    ],
)
def test_supported_ablations_are_explicit(sample_case, method, component):
    scenario, result = sample_case
    record = evaluate_method(method, result, scenario)
    assert record["changed_components"] == (component,)


def test_unknown_method_is_rejected(sample_case):
    scenario, result = sample_case
    with pytest.raises(ValueError):
        evaluate_method("neural_magic", result, scenario)


def test_unknown_scenario_is_rejected():
    with pytest.raises(ValueError):
        make_scenario("TYPO", seed=1)


def test_timestamp_manipulation_scenario_is_supported():
    scenario = make_scenario("S19", seed=1)
    observations, vessel = generate_observations(scenario)
    assert scenario.timestamp_manipulation is True
    assert vessel is not None
    assert vessel.timestamp == observations[-1].timestamp + 10.0


def test_method_comparison_uses_aligned_trials(tmp_path):
    path = run_method_comparison(
        ["S01", "S04"],
        trials=2,
        seed=4,
        output=tmp_path / "comparison",
        methods=("proposed", "physical_only"),
    )
    payload = path.read_text()
    assert '"status": "EXECUTED"' in payload
    assert '"method": "proposed"' in payload
    assert '"method": "physical_only"' in payload
