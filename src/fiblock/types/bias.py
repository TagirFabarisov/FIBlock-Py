"""Bias / offset: a constant error added to the value (FIBlock "Bias/Offset")."""
from __future__ import annotations

from ..core import FaultType, register


@register
class Bias(FaultType):
    """Add ``value`` (``relative=True``: multiply by ``1 + value``)."""

    def __init__(self, value: float, relative: bool = False):
        self.value = value
        self.relative = relative

    def apply(self, value, ctx):
        if self.relative:
            return value * (1.0 + self.value)
        return value + self.value
