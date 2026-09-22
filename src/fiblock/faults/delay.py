"""Delay: values arrive late (network / communication fault)."""
from __future__ import annotations

from typing import Any, List, Optional, Tuple

from .._spec import MISSING, register
from ..core import Fault
from ..distributions import as_distribution


@register
class Delay(Fault):
    """Values arrive late by ``delay`` time units.

    While active, each value passed in is queued with its time stamp and
    delivered when the host's time has advanced by ``delay``. Until the first
    late value is due, nothing arrives: the result is :data:`MISSING`, or, with
    ``gap="hold"``, the last correct value seen before activation. On
    deactivation the queue is dropped and values arrive on time again.
    ``delay`` may be a distribution; it is then sampled at each activation.
    """

    def __init__(self, target, delay: Any, gap: str = "missing", **kw):
        super().__init__(target, **kw)
        if gap not in ("missing", "hold"):
            raise ValueError("Delay.gap must be 'missing' or 'hold'")
        self.delay = delay
        self.gap = gap
        self._queue: List[Tuple[float, Any]] = []
        self._current_delay: Optional[float] = None
        self._last_before = MISSING
        self._last_delivered = MISSING

    def reset(self):
        self._queue = []
        self._current_delay = None
        self._last_before = MISSING
        self._last_delivered = MISSING

    def observe(self, value, ctx):
        if not self.active:
            self._last_before = value

    def on_activate(self, ctx):
        self._current_delay = as_distribution(self.delay).sample(ctx.rng)
        self._queue = []
        self._last_delivered = MISSING
        return {"delay": self._current_delay}

    def on_deactivate(self, ctx):
        self._queue = []

    def apply(self, value, ctx):
        self._queue.append((ctx.t, value))
        due_time = ctx.t - self._current_delay
        delivered = MISSING
        keep = []
        for (ts, v) in self._queue:
            if ts <= due_time:
                delivered = v
            else:
                keep.append((ts, v))
        if delivered is not MISSING:
            self._queue = keep
            self._last_delivered = delivered
            return delivered
        if self._last_delivered is not MISSING:
            return self._last_delivered   # between deliveries: the last late value stays visible
        if self.gap == "hold":
            return value if self._last_before is MISSING else self._last_before
        return MISSING

    def manifests(self, before, after):
        return before is not after and super().manifests(before, after)
