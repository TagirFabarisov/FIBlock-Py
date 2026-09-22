"""Mean time to repair: a random duration with a given mean (FIBlock "Mean Time To Repair")."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..core import FaultEffect, register
from ..distributions import Exponential, Normal


@register
@dataclass
class MeanTimeToRepair(FaultEffect):
    """Duration drawn at each activation with mean ``value``: exponential by
    default, or normal with standard deviation ``spread`` as in the original block."""
    value: float
    spread: Optional[float] = None
    _current: Optional[float] = field(default=None, init=False, repr=False, compare=False)

    def start(self, ctx):
        dist = Exponential(rate=1.0 / self.value) if self.spread is None else Normal(self.value, self.spread)
        self._current = max(0.0, dist.sample(ctx.rng))
        return {"duration": self._current}

    def expired(self, ctx):
        return ctx.t >= ctx.injector.t_activated + self._current
