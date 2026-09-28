"""Discrete and empirical distributions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from ..core.spec import register
from .base import Distribution


@register
@dataclass
class Choice(Distribution):
    """Draw one of ``values`` with optional ``probabilities``."""
    values: Sequence[float]
    probabilities: Sequence[float] = None  # type: ignore[assignment]

    def sample(self, rng):
        p = None if self.probabilities is None else np.asarray(self.probabilities, dtype=float)
        return float(rng.choice(np.asarray(self.values, dtype=float), p=p))


@register
@dataclass
class Poisson(Distribution):
    """Poisson count with mean ``lam`` (an integer-valued draw, returned as a float)."""
    lam: float

    def sample(self, rng):
        return float(rng.poisson(self.lam))


@register
@dataclass
class Binomial(Distribution):
    """Number of successes in ``n`` trials with probability ``p`` (returned as a float)."""
    n: int
    p: float

    def sample(self, rng):
        return float(rng.binomial(self.n, self.p))


@register
@dataclass
class Empirical(Distribution):
    """Resample recorded values with replacement."""
    samples: Sequence[float]

    def sample(self, rng):
        return float(rng.choice(np.asarray(self.samples, dtype=float)))
