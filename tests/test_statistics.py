"""Tests for statistical comparison utilities."""
import pytest
import numpy as np
from subsea.statistics import paired_bootstrap, permutation_test, cohens_d, mcnemar_test


class TestPairedBootstrap:
    def test_identical_scores_zero_diff(self):
        scores = [0.5] * 10
        result = paired_bootstrap(scores, scores)
        assert result["status"] == "EXECUTED"
        assert result["observed_difference"] == 0.0

    def test_different_scores_nonzero_diff(self):
        a = [0.8, 0.9, 0.7, 0.85, 0.75]
        b = [0.5, 0.6, 0.4, 0.55, 0.45]
        result = paired_bootstrap(a, b)
        assert result["observed_difference"] > 0
        assert result["ci_lower"] > 0  # A is clearly better

    def test_p_value_bounded(self):
        a = [0.8, 0.9, 0.7, 0.85, 0.75, 0.8, 0.9, 0.7]
        b = [0.5, 0.6, 0.4, 0.55, 0.45, 0.5, 0.6, 0.4]
        result = paired_bootstrap(a, b)
        assert 0 <= result["p_value"] <= 1

    def test_mismatched_length_raises(self):
        with pytest.raises(ValueError):
            paired_bootstrap([1, 2], [1, 2, 3])

    def test_too_few_observations_raises(self):
        with pytest.raises(ValueError):
            paired_bootstrap([1], [2])


class TestPermutationTest:
    def test_identical_scores_high_pvalue(self):
        scores = [0.5] * 10
        result = permutation_test(scores, scores)
        assert result["status"] == "EXECUTED"
        assert result["p_value"] >= 0.5

    def test_different_scores_low_pvalue(self):
        rng = np.random.default_rng(42)
        a = list(rng.normal(0.8, 0.05, 50))
        b = list(rng.normal(0.5, 0.05, 50))
        result = permutation_test(a, b, permutations=5000)
        assert result["p_value"] < 0.05


class TestCohensD:
    def test_no_difference(self):
        scores = [0.5] * 10
        d = cohens_d(scores, scores)
        assert d == 0.0

    def test_large_effect(self):
        a = [1.0, 1.0, 1.0, 1.0, 1.0]
        b = [0.0, 0.0, 0.0, 0.0, 0.0]
        d = cohens_d(a, b)
        assert d > 0.8  # Large effect size


class TestMcNemar:
    def test_identical_correctness(self):
        correct = [True, True, False, False, True]
        result = mcnemar_test(correct, correct)
        assert result["status"] == "EXECUTED"
        assert result["p_value"] == 1.0

    def test_different_correctness(self):
        a = [True, True, True, True, True, True, True, True, False, False]
        b = [False, False, False, False, True, True, True, True, True, True]
        result = mcnemar_test(a, b)
        assert result["status"] == "EXECUTED"
        assert "p_value" in result
