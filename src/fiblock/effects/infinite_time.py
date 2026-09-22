"""Infinite time: the error lasts until the end of the run (FIBlock "Infinite time")."""
from __future__ import annotations

from dataclasses import dataclass

from ..core import FaultEffect, register


@register
@dataclass
class InfiniteTime(FaultEffect):
    """Active until the end of the run or an explicit deactivation."""
