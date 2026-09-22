"""Failure probability: a fixed probability at every step (FIBlock "Failure probability").

This is the one event whose meaning depends on the step size; it is kept for
continuity with the original block. Prefer :class:`FailureRate` for a
step-independent stochastic activation.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..core import FaultEvent, register


@register
@dataclass
class FailureProbability(FaultEvent):
    value: float
    repeat: bool = True
    _fired: bool = field(default=False, init=False, repr=False, compare=False)

    def reset(self, ctx):
        self._fired = False

    def poll(self, ctx):
        if self._fired and not self.repeat:
            return None
        if ctx.rng.random() < self.value:
            self._fired = True
            return {"step_probability": float(self.value)}
        return None
