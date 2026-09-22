"""Failure time distribution: activation time drawn from any distribution (FIBlock "Probability Distribution")."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ..core import FaultEvent, register
from ..distributions import as_distribution


@register
@dataclass
class FailureTimeDistribution(FaultEvent):
    """Activation time ``t0 + offset + sample`` drawn at reset from ``distribution``
    (Weibull for wear-out, Gamma, LogNormal, a two-Weibull ``Mixture``, ...).
    ``repeat=True`` draws again after every deactivation, from the deactivation time."""
    distribution: Any
    repeat: bool = False
    offset: float = 0.0
    _scheduled: Optional[float] = field(default=None, init=False, repr=False, compare=False)
    _sample: Optional[float] = field(default=None, init=False, repr=False, compare=False)
    _armed: bool = field(default=False, init=False, repr=False, compare=False)

    def __post_init__(self):
        self.distribution = as_distribution(self.distribution)

    def _schedule(self, from_t, rng):
        self._sample = self.distribution.sample(rng)
        self._scheduled = from_t + self.offset + self._sample
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
