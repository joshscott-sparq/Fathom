"""Monte Carlo layer: PERT-beta sampling over story-level ranges (spec §4.1).

Each work item's 3-point estimate (R/O/P, with blanks substituted per §2.1) becomes
a PERT-beta distribution. Sampling and summing across items yields P10/P50/P80/P90
for effort; duration and cost derive from effort. A deterministic PERT point value
(the workbook-style weighted mean) stays available for the calibration/parity mode.
"""

from __future__ import annotations

import numpy as np

from ..models.results import Percentiles
from ..models.variables import Variables
from ..models.work_item import ThreePoint

# Standard PERT-beta shape parameter. Higher = more weight on the mode.
PERT_LAMBDA = 4.0


def deterministic_pert(tp: ThreePoint, variables: Variables) -> float:
    """Workbook weighted 3-point mean (§2.1), the calibration/parity value.

    AvgPts = (RealW*R + OptW*O + PesW*P) / (RealW + OptW + PesW), with blank O/P
    substituted by R.
    """
    o = tp.effective_optimistic
    p = tp.effective_pessimistic
    r = tp.realistic
    num = variables.real_weight * r + variables.opt_weight * o + variables.pes_weight * p
    den = variables.real_weight + variables.opt_weight + variables.pes_weight
    return num / den


def _sample_pert_beta(
    rng: np.random.Generator, a: float, m: float, b: float, size: int
) -> np.ndarray:
    """Sample a PERT-beta distribution with min=a, mode=m, max=b."""
    if b <= a:
        # Degenerate range (O == R == P): constant.
        return np.full(size, m, dtype=float)
    alpha = 1.0 + PERT_LAMBDA * (m - a) / (b - a)
    beta = 1.0 + PERT_LAMBDA * (b - m) / (b - a)
    return a + rng.beta(alpha, beta, size=size) * (b - a)


def simulate_points(
    items: list[ThreePoint],
    iterations: int = 10_000,
    seed: int = 12345,
    systemic_sigma: float = 0.0,
) -> tuple[np.ndarray, Percentiles]:
    """Sample summed effort points across all items.

    Work items are sampled from their PERT-beta distributions (independent
    scope/estimation noise). `systemic_sigma` > 0 adds a *correlated* per-iteration
    multiplier (a common-cause risk factor, lognormal with mean 1) applied to the
    whole project, so summing items does not artificially collapse the range —
    real engagements share systemic risk. Returns (per-iteration totals, percentiles).
    """
    rng = np.random.default_rng(seed)
    totals = np.zeros(iterations, dtype=float)
    for tp in items:
        totals += _sample_pert_beta(
            rng, tp.effective_optimistic, tp.realistic, tp.effective_pessimistic, iterations
        )
    if systemic_sigma > 0:
        # Lognormal with E[factor] = 1 so the median is unbiased; tails widen.
        factor = rng.lognormal(mean=-(systemic_sigma ** 2) / 2, sigma=systemic_sigma, size=iterations)
        totals *= factor
    return totals, _percentiles(totals)


def _percentiles(samples: np.ndarray) -> Percentiles:
    p10, p50, p80, p90 = np.percentile(samples, [10, 50, 80, 90])
    return Percentiles(p10=float(p10), p50=float(p50), p80=float(p80), p90=float(p90))


def derive_percentiles(samples: np.ndarray) -> Percentiles:
    """Percentiles for an already-sampled array (duration, cost)."""
    return _percentiles(samples)
