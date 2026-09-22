"""Noise: a random error drawn from a distribution at every value."""
from __future__ import annotations

from typing import Any

import numpy as np

from .._spec import register
from ..core import Fault
from ..distributions import Normal, as_distribution


@register
class Noise(Fault):
    """Add random noise: ``amplitude * sample`` from ``distribution`` (standard normal
    by default). ``relative=True`` scales the noise by the value itself, as in the
    original FIBlock's percentage noise (use ``distribution=Uniform(-1, 1)`` for that)."""

    def __init__(self, target, amplitude: float, relative: bool = False, distribution: Any = None, **kw):
        super().__init__(target, **kw)
        self.amplitude = amplitude
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
            return value * (1.0 + self.amplitude * s)
        return value + self.amplitude * s
