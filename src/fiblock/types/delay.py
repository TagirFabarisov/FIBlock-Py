"""Time delay: values arrive late (FIBlock "Time delay", value = delay)."""
from __future__ import annotations

from typing import Any, List, Optional, Tuple

from ..core import MISSING, FaultType, register
from ..distributions import as_distribution


@register
class Delay(FaultType):
    """Values arrive ``value`` time units late.

    While active, each value passed in is queued with its time stamp and
    delivered once the host's time has advanced by the delay. Until the first
    late value is due nothing arrives: the result is :data:`MISSING`, or, with
    ``gap="hold"``, the last correct value seen before activation. When the
    effect ends the queue is dropped and values arrive on time again.
    ``value`` may be a distribution; it is then sampled at each activation.
    """

    def __init__(self, value: Any, gap: str = "missing"):
        if gap not in ("missing", "hold"):
            raise ValueError("Delay.gap must be 'missing' or 'hold'")
        self.value = value
        self.gap = gap
        self._queue: List[Tuple[float, Any]] = []
        self._delay: Optional[float] = None
        self._last_before = MISSING
        self._last_delivered = MISSING

    def reset(self):
        self._queue = []
        self._delay = None
        self._last_before = MISSING
        self._last_delivered = MISSING

    def observe(self, value, ctx):
        if not ctx.injector.error_flag:
            self._last_before = value

    def on_activate(self, ctx):
        self._delay = as_distribution(self.value).sample(ctx.rng)
        self._queue = []
        self._last_delivered = MISSING
        return {"delay": self._delay}

    def on_deactivate(self, ctx):
        self._queue = []

    def apply(self, value, ctx):
        self._queue.append((ctx.t, value))
        due = ctx.t - self._delay
        delivered, keep = MISSING, []
        for ts, v in self._queue:
            if ts <= due:
                delivered = v
            else:
                keep.append((ts, v))
        if delivered is not MISSING:
            self._queue = keep
            self._last_delivered = delivered
            return delivered
        if self._last_delivered is not MISSING:
            return self._last_delivered      # between deliveries the last late value stays visible
        if self.gap == "hold":
            return value if self._last_before is MISSING else self._last_before
        return MISSING
