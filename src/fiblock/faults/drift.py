"""Drift: an error that grows linearly with time since activation."""
from __future__ import annotations

from .._spec import register
from ..core import Fault


@register
class Drift(Fault):
    """Offset growing linearly with time since activation: ``rate * elapsed``
    (``relative=True``: multiply by ``1 + rate * elapsed``)."""

    def __init__(self, target, rate: float, relative: bool = False, **kw):
        super().__init__(target, **kw)
        self.rate = rate
        self.relative = relative

    def apply(self, value, ctx):
        e = ctx.elapsed or 0.0
        if self.relative:
            return value * (1.0 + self.rate * e)
        return value + self.rate * e
