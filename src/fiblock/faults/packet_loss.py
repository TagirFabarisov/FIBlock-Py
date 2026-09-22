"""Packet loss: values are dropped (network / communication fault)."""
from __future__ import annotations

from typing import Any

from .._spec import MISSING, register
from ..core import Fault


@register
class PacketLoss(Fault):
    """Each value is dropped with ``probability`` (1.0 = every value while active).

    A dropped value becomes :data:`MISSING`, or ``substitute`` if one is given
    (the original FIBlock replaced dropped packets by a fixed value).
    """

    def __init__(self, target, probability: float = 1.0, substitute: Any = MISSING, **kw):
        super().__init__(target, **kw)
        self.probability = probability
        self.substitute = substitute

    def apply(self, value, ctx):
        if self.probability >= 1.0 or ctx.rng.random() < self.probability:
            return self.substitute
        return value
