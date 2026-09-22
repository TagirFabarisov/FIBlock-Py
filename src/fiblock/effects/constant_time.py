"""Constant time: the error lasts a fixed duration (FIBlock "Constant time")."""
from __future__ import annotations

from dataclasses import dataclass

from ..core import FaultEffect, register


@register
@dataclass
class ConstantTime(FaultEffect):
    value: float

    def start(self, ctx):
        return {"duration": float(self.value)}

    def expired(self, ctx):
        return ctx.t >= ctx.injector.t_activated + self.value
