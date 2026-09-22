"""Bias / offset: a constant error added to the value."""
from __future__ import annotations

from .._spec import register
from ..core import Fault


@register
class Bias(Fault):
    """Add a constant offset (``relative=True``: multiply by ``1 + magnitude``)."""

    def __init__(self, target, magnitude: float, relative: bool = False, **kw):
        super().__init__(target, **kw)
        self.magnitude = magnitude
        self.relative = relative

    def apply(self, value, ctx):
        if self.relative:
            return value * (1.0 + self.magnitude)
        return value + self.magnitude
