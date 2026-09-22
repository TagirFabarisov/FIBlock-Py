"""Noise: a random error drawn at every value (FIBlock "Noise", value = amplitude)."""
from __future__ import annotations

from typing import Any

import numpy as np

from ..core import FaultType, register
from ..distributions import Normal, as_distribution


@register
class Noise(FaultType):
    """Add ``value * sample`` with ``sample`` from ``distribution`` (standard normal by
    default). ``relative=True`` scales the noise by the signal itself; with
    ``distribution=Uniform(-1, 1)`` that is the original FIBlock's noise within
    ``value`` (as a fraction) of the correct value."""

    def __init__(self, value: float, relative: bool = False, distribution: Any = None):
        self.value = value
        self.relative = relative
        self.distribution = as_distribution(distribution) if distribution is not None else Normal(0.0, 1.0)

    def _draw(self, value, rng):
        if isinstance(value, np.ndarray):
            flat = np.array([self.distribution.sample(rng) for _ in range(value.size)], dtype=float)
            return flat.reshape(value.shape)
        return self.distribution.sample(rng)

    def apply(self, value, ctx):
        s = self._draw(value, ctx.rng)
        if self.relative:
            return value * (1.0 + self.value * s)
        return value + self.value * s
