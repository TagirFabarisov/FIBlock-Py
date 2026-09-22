"""Freeze: the value stays at the last correct reading (sensor freeze, stuck-at-current)."""
from __future__ import annotations

from .._spec import MISSING, register
from ..core import Fault


@register
class Freeze(Fault):
    """Hold the last correct value seen before activation."""

    def __init__(self, target, **kw):
        super().__init__(target, **kw)
        self._last = MISSING
        self._frozen = MISSING

    def reset(self):
        self._last = MISSING
        self._frozen = MISSING

    def observe(self, value, ctx):
        if not self.active:
            self._last = value

    def on_activate(self, ctx):
        self._frozen = self._last
        return {"frozen_value": None if self._frozen is MISSING else self._frozen}

    def apply(self, value, ctx):
        if self._frozen is MISSING:   # nothing observed yet: cannot freeze
            return value
        return self._frozen
