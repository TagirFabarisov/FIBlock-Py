"""Continuous distributions for times, durations, magnitudes and noise."""
from __future__ import annotations

from dataclasses import dataclass

from ..core.spec import register
from .base import Distribution


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
    """Parameters of the underlying normal (mean and std of log x)."""
    mean: float = 0.0
    sigma: float = 1.0

    def sample(self, rng):
        return float(rng.lognormal(self.mean, self.sigma))


@register
@dataclass
class Exponential(Distribution):
    """Exponential with ``rate`` events per unit time (mean 1/rate)."""
    rate: float

    def sample(self, rng):
        return float(rng.exponential(1.0 / self.rate))


@register
@dataclass
class Weibull(Distribution):
    """Weibull with ``shape`` k and ``scale`` λ: shape < 1 infant mortality,
    shape = 1 constant hazard, shape > 1 wear-out."""
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
