"""Drift: an error growing linearly with time since activation (FIBlock "Drift", value = slope)."""
from __future__ import annotations

from ..core import FaultType, register


@register
class Drift(FaultType):
    """Add ``value * elapsed`` (``relative=True``: multiply by ``1 + value * elapsed``)."""

    def __init__(self, value: float, relative: bool = False):
        self.value = value
        self.relative = relative

    def apply(self, value, ctx):
        e = ctx.elapsed or 0.0
        if self.relative:
            return value * (1.0 + self.value * e)
        return value + self.value * e
