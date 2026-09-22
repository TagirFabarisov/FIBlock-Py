"""Activation models: *when* a fault becomes active.

Every model is polled once per ``Campaign.advance`` while its fault is dormant
and eligible. ``poll`` returns ``None`` (stay dormant) or a dict of sampled
values to record (activate now). Models keep their own run-time state, which
the campaign resets.

Time is the host's time: any unit, any step size. Rates are per unit of that
time. ``PerStep`` is the one model whose meaning depends on the step size; it
exists for continuity with the original FIBlock's "failure probability per
execution".
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional, Sequence, Union

import numpy as np

from ._spec import Spec, register
from .distributions import Distribution, as_distribution

__all__ = ["Activation", "Immediately", "At", "Never", "SampledTime", "Rate", "TabulatedRate",
           "PerStep", "When", "Triggered"]


class Activation(Spec):
    def reset(self, ctx) -> None:
        return None

    def poll(self, ctx) -> Optional[dict]:
        return None

    def on_deactivated(self, ctx) -> None:
        return None

    def notify(self, event, ctx) -> None:
        """Receive every event of the campaign (used by :class:`Triggered`)."""
        return None


@register
@dataclass
class Immediately(Activation):
    """Activate on the first advance."""
    _fired: bool = field(default=False, init=False, repr=False, compare=False)

    def reset(self, ctx):
        self._fired = False

    def poll(self, ctx):
        if self._fired:
            return None
        self._fired = True
        return {"activation_time": ctx.t}


@register
@dataclass
class At(Activation):
    """Activate once, at the first advance whose time is >= ``time``."""
    time: float
    _fired: bool = field(default=False, init=False, repr=False, compare=False)

    def reset(self, ctx):
        self._fired = False

    def poll(self, ctx):
        if self._fired or ctx.t < self.time:
            return None
        self._fired = True
        return {"activation_time": ctx.t, "scheduled_time": float(self.time)}


@register
@dataclass
class Never(Activation):
    """Never activates by itself; only ``Campaign.activate`` can start it."""


@register
@dataclass
class SampledTime(Activation):
    """Activation time drawn from a distribution at reset (``t0 + offset + sample``).

    With ``repeat=True`` a new time is drawn after each deactivation, measured
    from the deactivation time: the classic mean-time-to-failure cycle.
    """
    distribution: Any
    repeat: bool = False
    offset: float = 0.0
    _scheduled: Optional[float] = field(default=None, init=False, repr=False, compare=False)
    _sample: Optional[float] = field(default=None, init=False, repr=False, compare=False)
    _armed: bool = field(default=False, init=False, repr=False, compare=False)

    def __post_init__(self):
        self.distribution = as_distribution(self.distribution)

    def _schedule(self, from_t, rng):
        self._sample = self.distribution.sample(rng)
        self._scheduled = from_t + self.offset + self._sample
        self._armed = True

    def reset(self, ctx):
        self._schedule(ctx.t, ctx.rng)

    def poll(self, ctx):
        if not self._armed or ctx.t < self._scheduled:
            return None
        self._armed = False
        return {"activation_time": ctx.t, "scheduled_time": self._scheduled, "sampled_delay": self._sample}

    def on_deactivated(self, ctx):
        if self.repeat:
            self._schedule(ctx.t, ctx.rng)


@register
@dataclass
class TabulatedRate(Spec):
    """A time-varying rate given by points (linear interpolation, clamped at the ends).

    The Python descendant of the hand-drawn "manual distribution" of the
    original FIBlock: the user specifies how the activation rate changes over time.
    """
    times: Sequence[float]
    rates: Sequence[float]

    def at(self, t: float) -> float:
        return float(np.interp(t, np.asarray(self.times, dtype=float), np.asarray(self.rates, dtype=float)))


@register
@dataclass
class Rate(Activation):
    """Activation as a Poisson-type process with a hazard ``rate`` per unit time.

    Over an advance of length ``dt`` the fault activates with probability
    ``1 - exp(-rate * dt)``, so the result does not depend on the step size.
    ``rate`` may be a number, a :class:`TabulatedRate`, or a callable ``t -> rate``.
    """
    rate: Any
    repeat: bool = True
    _fired: bool = field(default=False, init=False, repr=False, compare=False)

    def reset(self, ctx):
        self._fired = False

    def _rate_at(self, t):
        r = self.rate
        if hasattr(r, "at"):
            return float(r.at(t))
        if callable(r):
            return float(r(t))
        return float(r)

    def poll(self, ctx):
        if self._fired and not self.repeat:
            return None
        if ctx.dt <= 0:
            return None
        lam = self._rate_at(ctx.t)
        p = 1.0 - math.exp(-lam * ctx.dt)
        if ctx.rng.random() < p:
            self._fired = True
            return {"activation_time": ctx.t, "rate": lam, "step_probability": p}
        return None


@register
@dataclass
class PerStep(Activation):
    """Activate with a fixed ``probability`` at each advance (step-size dependent)."""
    probability: float
    repeat: bool = True
    _fired: bool = field(default=False, init=False, repr=False, compare=False)

    def reset(self, ctx):
        self._fired = False

    def poll(self, ctx):
        if self._fired and not self.repeat:
            return None
        if ctx.rng.random() < self.probability:
            self._fired = True
            return {"activation_time": ctx.t, "step_probability": float(self.probability)}
        return None


@register
@dataclass
class When(Activation):
    """Activate when ``condition(ctx)`` is true.

    ``edge=True`` (default) fires on the false-to-true transition only;
    ``edge=False`` fires whenever the condition holds while the fault is dormant.
    Conditions are Python callables and therefore not restorable from a spec.
    """
    condition: Callable[[Any], bool]
    edge: bool = True
    repeat: bool = True
    _prev: bool = field(default=False, init=False, repr=False, compare=False)
    _fired: bool = field(default=False, init=False, repr=False, compare=False)

    def reset(self, ctx):
        self._prev = False
        self._fired = False

    def poll(self, ctx):
        now = bool(self.condition(ctx))
        fire = now and (not self._prev if self.edge else True)
        self._prev = now
        if fire and not (self._fired and not self.repeat):
            self._fired = True
            return {"activation_time": ctx.t, "condition": repr(self.condition)}
        return None

    def spec(self):
        return {"kind": "When", "condition": {"kind": "Callable", "repr": repr(self.condition)},
                "edge": self.edge, "repeat": self.repeat}


@register
@dataclass
class Triggered(Activation):
    """Activate because another fault did something: a chained (conditional) fault.

    ``by`` names the source fault(s) (a name, a Fault object, or a list of them).
    ``on`` is the source event: ``"activated"``, ``"manifested"`` or ``"deactivated"``.
    ``delay`` is a number or a distribution (sampled per trigger) added to the
    source event time. ``probability`` lets a trigger fire only sometimes.
    """
    by: Any
    on: str = "activated"
    delay: Any = 0.0
    probability: float = 1.0
    repeat: bool = True
    _pending: List[dict] = field(default_factory=list, init=False, repr=False, compare=False)
    _fired: bool = field(default=False, init=False, repr=False, compare=False)

    def __post_init__(self):
        if self.on not in ("activated", "manifested", "deactivated"):
            raise ValueError("Triggered.on must be 'activated', 'manifested' or 'deactivated'")
        self.delay = as_distribution(self.delay)

    def sources(self) -> List[str]:
        items = self.by if isinstance(self.by, (list, tuple)) else [self.by]
        return [getattr(b, "name", b) for b in items]

    def reset(self, ctx):
        self._pending = []
        self._fired = False

    def notify(self, event, ctx):
        if event.kind != self.on or event.fault not in self.sources():
            return
        if event.fault == ctx.fault.name:
            return
        if self._fired and not self.repeat:
            return
        if self.probability < 1.0 and ctx.rng.random() >= self.probability:
            return
        d = self.delay.sample(ctx.rng)
        self._pending.append({"scheduled_time": event.time + d, "trigger_source": event.fault,
                              "trigger_event": event.kind, "trigger_delay": d})

    def poll(self, ctx):
        if not self._pending:
            return None
        due = [p for p in self._pending if p["scheduled_time"] <= ctx.t]
        if not due:
            return None
        first = min(due, key=lambda p: p["scheduled_time"])
        self._pending = [p for p in self._pending if p is not first]
        self._fired = True
        return {"activation_time": ctx.t, **first}

    def spec(self):
        return {"kind": "Triggered", "by": self.sources(), "on": self.on, "delay": self.delay.spec(),
                "probability": self.probability, "repeat": self.repeat}
