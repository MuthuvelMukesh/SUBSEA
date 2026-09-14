"""Statistical comparison utilities for method evaluation.

Implements paired bootstrap, permutation test, and effect size
calculations for comparing fusion methods on aligned trial data.
"""
from __future__ import annotations

from typing import Iterable

import numpy as np


def paired_bootstrap(
    scores_a: Iterable[float],
    scores_b: Iterable[float],
    *,
    statistic: str = "mean",
    resamples: int = 10000,
    seed: int = 42,
) -> dict[str, object]:
    """Paired bootstrap test for difference in means.

    Returns estimate, 95% CI, and p-value for H0: no difference.
    """
    a = np.asarray(list(scores_a), dtype=float)
    b = np.asarray(list(scores_b), dtype=float)
    if a.size != b.size or a.size < 2:
        raise ValueError("paired bootstrap requires equal-length inputs with at least 2 observations")
    if not np.all(np.isfinite(a)) or not np.all(np.isfinite(b)):
        raise ValueError("scores must be finite")
    if statistic != "mean":
        raise ValueError("only mean statistic is currently supported")

    observed_diff = float(np.mean(a) - np.mean(b))
    rng = np.random.default_rng(seed)
    diffs = a - b
    boot_diffs = np.empty(resamples)
    for i in range(resamples):
        indices = rng.choice(a.size, size=a.size, replace=True)
        boot_diffs[i] = np.mean(diffs[indices])

    lower = float(np.percentile(boot_diffs, 2.5))
    upper = float(np.percentile(boot_diffs, 97.5))
    # Two-sided p-value: fraction of bootstrap samples crossing zero
    p_value = float(np.mean(boot_diffs * observed_diff <= 0)) if observed_diff != 0 else 1.0

    return {
        "status": "EXECUTED",
        "statistic": statistic,
        "observed_difference": observed_diff,
        "ci_lower": lower,
        "ci_upper": upper,
        "p_value": p_value,
        "resamples": resamples,
        "seed": seed,
        "n": int(a.size),
    }


def permutation_test(
    scores_a: Iterable[float],
    scores_b: Iterable[float],
    *,
    permutations: int = 10000,
    seed: int = 42,
) -> dict[str, object]:
    """Two-sided permutation test for difference in means."""
    a = np.asarray(list(scores_a), dtype=float)
    b = np.asarray(list(scores_b), dtype=float)
    if a.size != b.size or a.size < 2:
        raise ValueError("permutation test requires equal-length inputs with at least 2 observations")
    if not np.all(np.isfinite(a)) or not np.all(np.isfinite(b)):
        raise ValueError("scores must be finite")

    observed_diff = float(np.mean(a) - np.mean(b))
    rng = np.random.default_rng(seed)
    combined = np.concatenate([a, b])
    n = a.size
    count = 0
    for _ in range(permutations):
        rng.shuffle(combined)
        perm_diff = np.mean(combined[:n]) - np.mean(combined[n:])
        if abs(perm_diff) >= abs(observed_diff):
            count += 1

    return {
        "status": "EXECUTED",
        "observed_difference": observed_diff,
        "p_value": float(count / permutations),
        "permutations": permutations,
        "seed": seed,
        "n": int(n),
    }


def cohens_d(scores_a: Iterable[float], scores_b: Iterable[float]) -> float:
    """Cohen's d effect size for paired differences."""
    a = np.asarray(list(scores_a), dtype=float)
    b = np.asarray(list(scores_b), dtype=float)
    if a.size != b.size or a.size < 2:
        raise ValueError("effect size requires equal-length inputs with at least 2 observations")
    diffs = a - b
    return float(np.mean(diffs) / max(np.std(diffs, ddof=1), 1e-12))


def mcnemar_test(
    correct_a: Iterable[bool],
    correct_b: Iterable[bool],
) -> dict[str, object]:
    """McNemar's test for paired nominal data (correct/incorrect)."""
    ca = np.asarray(list(correct_a), dtype=bool)
    cb = np.asarray(list(correct_b), dtype=bool)
    if ca.size != cb.size or ca.size < 1:
        raise ValueError("McNemar test requires equal-length inputs")

    # b01: A wrong, B right; b10: A right, B wrong
    b01 = int(np.sum(~ca & cb))
    b10 = int(np.sum(ca & ~cb))
    n_discordant = b01 + b10
    if n_discordant == 0:
        return {"status": "EXECUTED", "b01": b01, "b10": b10, "chi2": 0.0, "p_value": 1.0, "n": int(ca.size)}

    # Chi-squared with continuity correction
    chi2 = (abs(b01 - b10) - 1) ** 2 / n_discordant if n_discordant > 0 else 0.0
    from scipy.stats import chi2 as chi2_dist
    p_value = float(1 - chi2_dist.cdf(chi2, df=1))

    return {
        "status": "EXECUTED",
        "b01": b01,
        "b10": b10,
        "chi2": float(chi2),
        "p_value": p_value,
        "n": int(ca.size),
    }
