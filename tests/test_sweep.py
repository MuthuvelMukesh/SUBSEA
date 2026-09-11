import json

from subsea.experiments import run_attack_severity_sweep, run_trials


def test_trial_manifest_contains_auditable_components(tmp_path):
    path = run_trials("S04", 1, 3, tmp_path / "trial", attack="ais_spoofing")
    prediction = json.loads(path.read_text())["predictions"][0]
    assert {"physical_confidence", "association_confidence", "reliability", "uncertainty", "hypothesis_scores"} <= prediction.keys()
    assert path and json.loads(path.read_text())["latencies"][0]["latency_ms"] >= 0


def test_attack_severity_sweep_is_reproducible_in_shape(tmp_path):
    path = run_attack_severity_sweep("S04", 1, 3, tmp_path / "sweep", severities=(0.0, 0.5, 1.0))
    payload = json.loads(path.read_text())
    assert payload["status"] == "EXECUTED"
    assert [row["severity"] for row in payload["rows"]] == [0.0, 0.5, 1.0]