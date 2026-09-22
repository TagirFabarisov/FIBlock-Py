"""Mean time to failure: a random activation time with a given mean (FIBlock "Mean Time To Failure")."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..core import FaultEvent, register
from ..distributions import Exponential, Normal


@register
@dataclass
class MeanTimeToFailure(FaultEvent):
    """Activation time drawn with mean ``value``: exponential (constant failure
    rate) by default, or normal with standard deviation ``spread`` as in the
    original block. ``repeat=True`` draws a new time after every deactivation,
    measured from the deactivation: the classic failure/repair cycle.
    """
    value: float
    spread: Optional[float] = None
    repeat: bool = True
    _scheduled: Optional[float] = field(default=None, init=False, repr=False, compare=False)
    _sample: Optional[float] = field(default=None, init=False, repr=False, compare=False)
    _armed: bool = field(default=False, init=False, repr=False, compare=False)

    def _distribution(self):
        if self.spread is None:
            return Exponential(rate=1.0 / self.value)
        return Normal(self.value, self.spread)

    def _schedule(self, from_t, rng):
        s = max(0.0, self._distribution().sample(rng))
        self._sample = s
        self._scheduled = from_t + s
        self._armed = True

    def reset(self, ctx):
        self._schedule(ctx.t, ctx.rng)

    def poll(self, ctx):
        if not self._armed or ctx.t < self._scheduled:
            return None
        self._armed = False
        return {"scheduled_time": self._scheduled, "time_to_failure": self._sample}

    def on_deactivated(self, ctx):
        if self.repeat:
            self._schedule(ctx.t, ctx.rng)
