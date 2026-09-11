import json

import pytest

from subsea.adversarial import apply_attack
from subsea.experiments import run_trials
from subsea.metrics import adversarial_error_rate, false_high_escalation_rate
from subsea.models import VesselObservation


def test_apply_attack_is_immutable_and_records_metadata():
    vessel = VesselObservation("v", 1.0, (1.0, 1.0), 2.0, 90.0)
    attacked = apply_attack(vessel, "ais_spoofing", severity=0.5)
    assert attacked is not vessel
    assert attacked.position != vessel.position
    assert attacked.metadata["attack"] == "ais_position_spoofing"
    assert vessel.position == (1.0, 1.0)


def test_run_trials_records_attack_and_is_reproducible(tmp_path):
    first_path = run_trials("S04", trials=3, seed=10, output=tmp_path / "first", attack="ais_spoofing", attack_severity=0.5)
    second_path = run_trials("S04", trials=3, seed=10, output=tmp_path / "second", attack="ais_spoofing", attack_severity=0.5)
    first = json.loads(first_path.read_text())
    second = json.loads(second_path.read_text())
    assert first["status"] == "EXECUTED"
    assert first["predictions"] == second["predictions"]
    assert all(item["attack"] == "ais_spoofing" for item in first["predictions"])
    assert all(item["attack_applied"] for item in first["predictions"])
    assert first["metrics"]["AER"]["status"] == "EXECUTED"
    assert first["metrics"]["FHER"]["status"] == "NOT EXECUTED"


def test_no_attack_does_not_report_aer(tmp_path):
    path = run_trials("S04", trials=2, seed=10, output=tmp_path / "no-attack", attack="none")
    manifest = json.loads(path.read_text())
    assert manifest["metrics"]["AER"] == {
        "status": "NOT EXECUTED",
        "value": None,
        "reason": "cohort must contain at least one trial",
    }


def test_run_trials_executes_fher_for_benign_scenario(tmp_path):
    path = run_trials("S01", trials=2, seed=10, output=tmp_path / "benign")
    manifest = json.loads(path.read_text())
    assert manifest["metrics"]["AER"]["status"] == "NOT EXECUTED"
    assert manifest["metrics"]["FHER"]["status"] == "EXECUTED"


def test_run_trials_rejects_invalid_count_and_overwrite(tmp_path):
    with pytest.raises(ValueError):
        run_trials("S04", trials=0, seed=1, output=tmp_path / "zero")
    output = tmp_path / "existing"
    output.mkdir()
    with pytest.raises(FileExistsError):
        run_trials("S04", trials=1, seed=1, output=output)
    with pytest.raises(ValueError):
        run_trials("S01", trials=1, seed=1, output=tmp_path / "invalid-attack", attack="invalid")


def test_aer_and_fher_use_explicit_cohorts():
    assert adversarial_error_rate(["T0", "TX", "T2"], [True, True, True]) == pytest.approx(1 / 3)
    assert false_high_escalation_rate(["T3", "T2", "T1"], [True, True, True]) == pytest.approx(2 / 3)
    with pytest.raises(ValueError):
        adversarial_error_rate(["T0"], [False])
    with pytest.raises(ValueError):
        false_high_escalation_rate(["T0"], [False])


def test_aer_and_fher_reject_invalid_cohorts():
    with pytest.raises(ValueError):
        adversarial_error_rate([], [])
    with pytest.raises(ValueError):
        false_high_escalation_rate(["T0"], [])
    with pytest.raises(ValueError):
        adversarial_error_rate(["T0"], [True, False])
