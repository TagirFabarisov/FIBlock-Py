"""Packet loss: values are dropped (FIBlock "Package drop", value = drop probability)."""
from __future__ import annotations

from typing import Any

from ..core import MISSING, FaultType, register


@register
class PacketLoss(FaultType):
    """Drop each value with probability ``value`` (1.0: every value while active).

    A dropped value becomes :data:`MISSING`, or ``substitute`` if one is given
    (the original FIBlock replaced dropped packets by a fixed value).
    """

    def __init__(self, value: float = 1.0, substitute: Any = MISSING):
        self.value = value
        self.substitute = substitute

    def apply(self, value, ctx):
        if self.value >= 1.0 or ctx.rng.random() < self.value:
            return self.substitute
        return value
