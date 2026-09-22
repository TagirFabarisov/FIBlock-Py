"""Duration distribution: the error lasts a random time from any distribution
(FIBlock's Weibull / Gamma / Exponential / ... effect durations)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ..core import FaultEffect, register
from ..distributions import as_distribution


@register
@dataclass
class DurationDistribution(FaultEffect):
    distribution: Any
    _current: Optional[float] = field(default=None, init=False, repr=False, compare=False)

    def __post_init__(self):
        self.distribution = as_distribution(self.distribution)

    def start(self, ctx):
        self._current = self.distribution.sample(ctx.rng)
        return {"duration": self._current}

    def expired(self, ctx):
        return ctx.t >= ctx.injector.t_activated + self._current
