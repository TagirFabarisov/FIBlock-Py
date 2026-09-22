"""Once: the error appears for a single step (FIBlock "Once")."""
from __future__ import annotations

from dataclasses import dataclass

from ..core import FaultEffect, register


@register
@dataclass
class Once(FaultEffect):
    """Deactivated at the first step after the activation step."""

    def expired(self, ctx):
        return ctx.t > ctx.injector.t_activated
