"""Duration (exposure) models: *how long* a fault stays active.

``start(ctx)`` is called at activation and may return sampled values to record.
``expired(ctx)`` is polled at every advance while the fault is active; the fault
is deactivated at the advance where it first returns True. Explicit
deactivation is always available through ``Campaign.deactivate``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from ._spec import Spec, register
from .distributions import as_distribution

__all__ = ["Duration", "Permanent", "Once", "Fixed", "SampledDuration", "Until"]


class Duration(Spec):
    def start(self, ctx) -> Optional[dict]:
        return None

    def expired(self, ctx) -> bool:
        return False


@register
@dataclass
class Permanent(Duration):
    """Active until the end of the run or an explicit deactivation."""


@register
@dataclass
class Once(Duration):
    """Active for a single step: deactivated at the next advance after activation."""

    def expired(self, ctx):
        return ctx.t > ctx.fault.t_activated


@register
@dataclass
class Fixed(Duration):
    """Active for ``duration`` time units."""
    duration: float

    def start(self, ctx):
        return {"duration": float(self.duration)}

    def expired(self, ctx):
        return ctx.t >= ctx.fault.t_activated + self.duration


@register
@dataclass
class SampledDuration(Duration):
    """Duration drawn from a distribution at each activation (mean-time-to-repair style)."""
    distribution: Any
    _current: Optional[float] = field(default=None, init=False, repr=False, compare=False)

    def __post_init__(self):
        self.distribution = as_distribution(self.distribution)

    def start(self, ctx):
        self._current = self.distribution.sample(ctx.rng)
        return {"duration": self._current}

    def expired(self, ctx):
        return ctx.t >= ctx.fault.t_activated + self._current


@register
@dataclass
class Until(Duration):
    """Active until ``condition(ctx)`` becomes true (not restorable from a spec)."""
    condition: Callable[[Any], bool]

    def expired(self, ctx):
        return bool(self.condition(ctx))

    def spec(self):
        return {"kind": "Until", "condition": {"kind": "Callable", "repr": repr(self.condition)}}
