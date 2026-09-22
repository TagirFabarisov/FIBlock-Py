"""Deterministic event: activate at a fixed time (FIBlock "Deterministic")."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..core import FaultEvent, register


@register
@dataclass
class Deterministic(FaultEvent):
    """Activate once, at the first step whose time is >= ``time`` (default 0: immediately)."""
    time: float = 0.0
    _fired: bool = field(default=False, init=False, repr=False, compare=False)

    def reset(self, ctx):
        self._fired = False

    def poll(self, ctx):
        if self._fired or ctx.t < self.time:
            return None
        self._fired = True
        return {"scheduled_time": float(self.time)}
