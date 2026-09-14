"""Tests for Monte Carlo experiments."""
import pytest
import json
from subsea.experiments import run_monte_carlo


class TestMonteCarlo:
    def test_basic_execution(self, tmp_path):
        path = run_monte_carlo(["S01", "S04"], 10, 42, tmp_path / "mc")
        manifest = json.loads(path.read_text())
        assert manifest["status"] == "EXECUTED"
        assert manifest["experiment_type"] == "monte_carlo"
        assert manifest["total_records"] == 20  # 2 scenarios * 10 trials * 1 method
        assert manifest["seed"] == 42

    def test_records_have_required_fields(self, tmp_path):
        path = run_monte_carlo(["S04"], 5, 42, tmp_path / "mc")
        manifest = json.loads(path.read_text())
        for record in manifest["records"]:
            assert "master_seed" in record
            assert "trial_seed" in record
            assert "scenario_id" in record
            assert "method" in record
            assert "decision" in record
            assert "confidence" in record
            assert "uncertainty" in record
            assert record["decision"] in {"T0", "T1", "T2", "T3", "TX"}

    def test_reproducibility(self, tmp_path):
        path1 = run_monte_carlo(["S04"], 10, 42, tmp_path / "mc1")
        path2 = run_monte_carlo(["S04"], 10, 42, tmp_path / "mc2")
        m1 = json.loads(path1.read_text())
        m2 = json.loads(path2.read_text())
        # Same seeds should produce identical decisions
        for r1, r2 in zip(m1["records"], m2["records"]):
            assert r1["decision"] == r2["decision"]
            assert r1["trial_seed"] == r2["trial_seed"]

    def test_with_attack(self, tmp_path):
        path = run_monte_carlo(
            ["S04"], 5, 42, tmp_path / "mc_attack",
            attack="ais_spoofing", attack_severity=0.5,
        )
        manifest = json.loads(path.read_text())
        assert manifest["attack"] == "ais_spoofing"
        assert manifest["attack_severity"] == 0.5

    def test_multiple_methods(self, tmp_path):
        path = run_monte_carlo(
            ["S04"], 5, 42, tmp_path / "mc_methods",
            methods=("proposed", "physical_only"),
        )
        manifest = json.loads(path.read_text())
        assert manifest["total_records"] == 10  # 1 scenario * 5 trials * 2 methods

    def test_invalid_trials_raises(self, tmp_path):
        with pytest.raises(ValueError):
            run_monte_carlo(["S04"], 0, 42, tmp_path / "mc_bad")
