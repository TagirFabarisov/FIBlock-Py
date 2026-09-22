"""Stuck-at: the value is replaced by a fixed one (FIBlock "Stuck-at-0" and the like)."""
from __future__ import annotations

from typing import Any

from ..core import FaultType, register


@register
class StuckAt(FaultType):
    """Replace by ``value``."""

    def __init__(self, value: Any):
        self.value = value

    def apply(self, value, ctx):
        return self.value
