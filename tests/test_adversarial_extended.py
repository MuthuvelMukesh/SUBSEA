"""Tests for extended adversarial attacks and severity sweeps."""
import pytest
import json
from subsea.adversarial import apply_attack, SUPPORTED_ATTACKS
from subsea.models import VesselObservation


class TestSupportedAttacks:
    def test_all_five_attacks_supported(self):
        expected = {"none", "ais_spoofing", "transponder_suppression",
                    "timestamp_manipulation", "spatial_manipulation", "combined_evasion"}
        assert SUPPORTED_ATTACKS == expected


class TestSpatialManipulation:
    def test_shifts_position(self):
        v = VesselObservation("v1", 10.0, (2.0, 1.0), 4.0, 90.0)
        attacked = apply_attack(v, "spatial_manipulation", 0.5)
        assert attacked.position != v.position
        assert attacked.metadata.get("attack") == "spatial_manipulation"

    def test_severity_zero_returns_original(self):
        v = VesselObservation("v1", 10.0, (2.0, 1.0), 4.0, 90.0)
        result = apply_attack(v, "spatial_manipulation", 0.0)
        assert result.position == v.position

    def test_severity_scales_distance(self):
        v = VesselObservation("v1", 10.0, (2.0, 1.0), 4.0, 90.0)
        low = apply_attack(v, "spatial_manipulation", 0.2)
        high = apply_attack(v, "spatial_manipulation", 0.8)
        import numpy as np
        d_low = np.linalg.norm(np.array(low.position) - np.array(v.position))
        d_high = np.linalg.norm(np.array(high.position) - np.array(v.position))
        assert d_high > d_low


class TestCombinedEvasion:
    def test_applies_multiple_manipulations(self):
        v = VesselObservation("v1", 10.0, (2.0, 1.0), 4.0, 90.0)
        attacked = apply_attack(v, "combined_evasion", 0.5)
        assert attacked.position != v.position
        assert attacked.timestamp != v.timestamp
        assert attacked.position_uncertainty > v.position_uncertainty

    def test_severity_zero_returns_original(self):
        v = VesselObservation("v1", 10.0, (2.0, 1.0), 4.0, 90.0)
        result = apply_attack(v, "combined_evasion", 0.0)
        assert result == v


class TestSeverityBaselines:
    @pytest.mark.parametrize("attack", [a for a in SUPPORTED_ATTACKS if a != "none"])
    def test_zero_severity_reproduces_benign(self, attack):
        v = VesselObservation("v1", 10.0, (2.0, 1.0), 4.0, 90.0)
        result = apply_attack(v, attack, 0.0)
        assert result.position == v.position
        assert result.timestamp == v.timestamp

    def test_invalid_severity_raises(self):
        v = VesselObservation("v1", 10.0, (2.0, 1.0), 4.0, 90.0)
        with pytest.raises(ValueError):
            apply_attack(v, "ais_spoofing", -0.1)
        with pytest.raises(ValueError):
            apply_attack(v, "ais_spoofing", 1.1)


class TestSeveritySweep:
    def test_sweep_with_new_attacks(self, tmp_path):
        from subsea.experiments import run_attack_severity_sweep
        for attack in ("spatial_manipulation", "combined_evasion"):
            path = run_attack_severity_sweep(
                "S04", 5, 42, tmp_path / f"sweep-{attack}",
                attack=attack, severities=(0.0, 0.5, 1.0),
            )
            manifest = json.loads(path.read_text())
            assert manifest["status"] == "EXECUTED"
            assert len(manifest["rows"]) == 3
