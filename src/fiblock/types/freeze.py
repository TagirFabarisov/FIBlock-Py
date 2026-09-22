"""Freeze: the value stays at the last correct reading (FIBlock "Stuck-at" at the current value)."""
from __future__ import annotations

from ..core import MISSING, FaultType, register


@register
class Freeze(FaultType):
    """Hold the last correct value seen before activation. No fault value."""

    def __init__(self):
        self._last = MISSING
        self._frozen = MISSING

    def reset(self):
        self._last = MISSING
        self._frozen = MISSING

    def observe(self, value, ctx):
        if not ctx.injector.error_flag:
            self._last = value

    def on_activate(self, ctx):
        self._frozen = self._last
        return {"frozen_value": None if self._frozen is MISSING else self._frozen}

    def apply(self, value, ctx):
        if self._frozen is MISSING:   # nothing observed yet: cannot freeze
            return value
        return self._frozen
