"""Scale: the value is multiplied by a factor (capacity loss, gain error)."""
from __future__ import annotations

from .._spec import register
from ..core import Fault


@register
class Scale(Fault):
    """Multiply by ``factor`` (e.g. a pump delivering 60 % of nominal capacity)."""

    def __init__(self, target, factor: float, **kw):
        super().__init__(target, **kw)
        self.factor = factor

    def apply(self, value, ctx):
        return value * self.factor
