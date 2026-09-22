"""Stuck-at: the value is replaced by a fixed one (stuck-at-0, stuck-at-max, ...)."""
from __future__ import annotations

from typing import Any

from .._spec import register
from ..core import Fault


@register
class StuckAt(Fault):
    """Replace by a fixed ``value``."""

    def __init__(self, target, value: Any, **kw):
        super().__init__(target, **kw)
        self.value = value

    def apply(self, value, ctx):
        return self.value
