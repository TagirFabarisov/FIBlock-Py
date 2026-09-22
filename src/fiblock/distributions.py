"""Probability distributions used for stochastic activation times, durations,
magnitudes and noise.

A distribution is any object with ``sample(rng) -> float`` where ``rng`` is a
``numpy.random.Generator``. The classes below are plain dataclasses so that
their parameters are visible, editable and serialisable. ``as_distribution``
also accepts a bare number (a constant), a callable ``rng -> float`` and any
SciPy-style frozen distribution (an object with ``rvs``).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

import numpy as np

from ._spec import Spec, register


class Distribution(Spec):
    """Base class. Subclasses implement ``sample``."""

    def sample(self, rng: np.random.Generator) -> float:  # pragma: no cover - abstract
        raise NotImplementedError


@register
@dataclass
class Constant(Distribution):
    value: float

    def sample(self, rng):
        return float(self.value)


@register
@dataclass
class Uniform(Distribution):
    low: float
    high: float

    def sample(self, rng):
        return float(rng.uniform(self.low, self.high))


@register
@dataclass
class Normal(Distribution):
    mean: float = 0.0
    std: float = 1.0

    def sample(self, rng):
        return float(rng.normal(self.mean, self.std))


@register
@dataclass
class LogNormal(Distribution):
    """Parameters are those of the underlying normal (mean and std of log x)."""
    mean: float = 0.0
    sigma: float = 1.0

    def sample(self, rng):
        return float(rng.lognormal(self.mean, self.sigma))


@register
@dataclass
class Exponential(Distribution):
    """Exponential with ``rate`` events per unit time (mean = 1/rate)."""
    rate: float

    def sample(self, rng):
        return float(rng.exponential(1.0 / self.rate))


@register
@dataclass
class Weibull(Distribution):
    """Weibull with ``shape`` k and ``scale`` lambda.

    shape < 1: decreasing hazard (infant mortality); shape = 1: constant hazard
    (exponential); shape > 1: increasing hazard (wear-out).
    """
    shape: float
    scale: float = 1.0

    def sample(self, rng):
        return float(self.scale * rng.weibull(self.shape))


@register
@dataclass
class Gamma(Distribution):
    shape: float
    scale: float = 1.0

    def sample(self, rng):
        return float(rng.gamma(self.shape, self.scale))


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
class Mixture(Distribution):
    """Pick a component with probability ``weights`` and sample from it
    (for example a two-Weibull mixture)."""
    components: Sequence[Distribution]
    weights: Sequence[float] = None  # type: ignore[assignment]

    def sample(self, rng):
        n = len(self.components)
        w = None if self.weights is None else np.asarray(self.weights, dtype=float) / float(np.sum(self.weights))
        i = int(rng.choice(n, p=w))
        return self.components[i].sample(rng)


@register
@dataclass
class Empirical(Distribution):
    """Resample from recorded values (with replacement)."""
    samples: Sequence[float]

    def sample(self, rng):
        return float(rng.choice(np.asarray(self.samples, dtype=float)))


@dataclass
class FromCallable(Distribution):
    """Wrap any ``fn(rng) -> float``. Not serialisable (the spec records ``repr``)."""
    fn: Callable[[np.random.Generator], float]

    def sample(self, rng):
        return float(self.fn(rng))

    def spec(self):
        return {"kind": "FromCallable", "repr": repr(self.fn)}


@dataclass
class Scipy(Distribution):
    """Adapter for a SciPy frozen distribution (anything with ``rvs``)."""
    frozen: Any

    def sample(self, rng):
        return float(self.frozen.rvs(random_state=rng))

    def spec(self):
        return {"kind": "Scipy", "repr": repr(self.frozen)}


def as_distribution(x) -> Distribution:
    """Coerce a number, callable, SciPy object or Distribution into a Distribution."""
    if isinstance(x, Distribution):
        return x
    if isinstance(x, (int, float, np.integer, np.floating)) and not isinstance(x, bool):
        return Constant(float(x))
    if hasattr(x, "rvs"):
        return Scipy(x)
    if callable(x):
        return FromCallable(x)
    raise TypeError(f"cannot interpret {x!r} as a distribution")
