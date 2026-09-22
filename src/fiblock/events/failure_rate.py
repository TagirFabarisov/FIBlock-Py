"""Failure rate: a hazard rate per unit time, constant or varying over time
(FIBlock "Failure rate distribution" / "Manual distribution", made step-independent)."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Sequence

import numpy as np

from ..core import FaultEvent, Spec, register


@register
@dataclass
class TabulatedRate(Spec):
    """A rate given by points over time, linearly interpolated and clamped at
    the ends: the Python form of the hand-drawn curve of the original block."""
    times: Sequence[float]
    rates: Sequence[float]

    def at(self, t: float) -> float:
        return float(np.interp(t, np.asarray(self.times, dtype=float), np.asarray(self.rates, dtype=float)))


@register
@dataclass
class FailureRate(FaultEvent):
    """Over a step of length ``dt`` the fault activates with probability
    ``1 - exp(-rate * dt)``, so the result does not depend on the step size.
    ``value`` is a number, a :class:`TabulatedRate`, or a callable ``t -> rate``."""
    value: Any
    repeat: bool = True
    _fired: bool = field(default=False, init=False, repr=False, compare=False)

    def reset(self, ctx):
        self._fired = False

    def rate_at(self, t: float) -> float:
        r = self.value
        if hasattr(r, "at"):
            return float(r.at(t))
        if callable(r):
            return float(r(t))
        return float(r)

    def poll(self, ctx):
        if (self._fired and not self.repeat) or ctx.dt <= 0:
            return None
        lam = self.rate_at(ctx.t)
        p = 1.0 - math.exp(-lam * ctx.dt)
        if ctx.rng.random() < p:
            self._fired = True
            return {"rate": lam, "step_probability": p}
        return None
