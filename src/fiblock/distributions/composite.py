"""Distributions built from other distributions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from ..core.spec import register
from .base import Distribution


@register
@dataclass
class Mixture(Distribution):
    """Pick a component with probability ``weights`` and sample from it
    (for example the two-Weibull mixture of the original FIBlock)."""
    components: Sequence[Distribution]
    weights: Sequence[float] = None  # type: ignore[assignment]

    def sample(self, rng):
        w = None if self.weights is None else np.asarray(self.weights, dtype=float) / float(np.sum(self.weights))
        i = int(rng.choice(len(self.components), p=w))
        return self.components[i].sample(rng)
