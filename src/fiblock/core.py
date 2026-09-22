"""The fault abstraction.

A :class:`Fault` is attached to a *target* (a name chosen by the host
simulator for an injection point: a signal, a parameter, a message link). It
is described by three independent choices, each an ordinary object:

* what the error looks like: the subclass and its parameters (``apply``);
* when it activates: an :mod:`fiblock.activation` model;
* how long it lasts: a :mod:`fiblock.duration` model.

The library never touches simulator state itself. The host passes a value
through ``Campaign.inject(target, value, t)`` and receives the value as the
active faults on that target leave it, or :data:`MISSING` when nothing arrives.
"""
from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import numpy as np

from ._spec import MISSING, Spec, _to_plain

__all__ = ["Fault", "FaultContext", "Outcome", "MISSING", "changed"]


def changed(before, after) -> bool:
    """True when ``after`` differs from ``before`` (arrays compared elementwise)."""
    if before is MISSING or after is MISSING:
        return before is not after
    try:
        if isinstance(before, np.ndarray) or isinstance(after, np.ndarray):
            return not np.array_equal(before, after)
        return bool(before != after)
    except Exception:
        return True


@dataclass
class FaultContext:
    """What a fault sees when it is polled or applied.

    ``t`` is the host's current time in the host's own units; ``dt`` is the time
    since the previous ``advance`` (0 on the first). ``rng`` is the fault's own
    seeded generator. ``host`` is whatever object the host chose to pass along
    (for conditions that need to look at simulator state).
    """
    t: float
    dt: float
    rng: np.random.Generator
    fault: "Fault"
    campaign: Any = None
    host: Any = None

    @property
    def t_activated(self) -> Optional[float]:
        return self.fault.t_activated

    @property
    def elapsed(self) -> Optional[float]:
        """Time since the fault's current activation, or None while dormant."""
        if self.fault.t_activated is None:
            return None
        return self.t - self.fault.t_activated


@dataclass
class Outcome:
    """Result of one injection call."""
    value: Any
    target: str
    t: float
    manifested: Tuple[str, ...] = ()   # names of faults that actually altered the value
    applied: Tuple[str, ...] = ()      # names of active faults whose apply() ran

    @property
    def missing(self) -> bool:
        return self.value is MISSING

    @property
    def clean(self) -> bool:
        return not self.manifested


class Fault(Spec):
    """Base class for all faults. Subclass it and implement ``apply``.

    Parameters of the subclass constructor are the fault's *parameters*: plain
    attributes that an external program may read, edit, sample or sweep. They
    are reported in every event and in the spec. Run-time state (``active``,
    ``t_activated``, ...) is kept separately and reset by the campaign.

    Hooks a subclass may override:

    * ``apply(value, ctx)``      the error: return the corrupted value or ``MISSING``;
    * ``observe(value, ctx)``    sees every pre-fault value on the target, active or not;
    * ``on_activate(ctx)``       may return a dict of sampled parameters to record;
    * ``on_deactivate(ctx)``     clean-up;
    * ``reset()``                clear subclass state at campaign reset;
    * ``manifests(before, after)`` decide whether a change counts as an error.
    """

    _BASE_ARGS = ("target", "activation", "duration", "name", "enabled", "max_activations")

    def __init__(self, target: str, *, activation=None, duration=None, name: Optional[str] = None,
                 enabled: bool = True, max_activations: Optional[int] = None):
        from .activation import Immediately
        from .duration import Permanent
        self.target = str(target)
        self.activation = activation if activation is not None else Immediately()
        self.duration = duration if duration is not None else Permanent()
        self.name = name
        self.enabled = bool(enabled)
        self.max_activations = max_activations
        self._campaign = None
        self.rng: Optional[np.random.Generator] = None
        self.seed_info: Optional[Dict[str, int]] = None
        self._reset_state()

    # ------------------------------------------------------------------ state
    def _reset_state(self):
        self.active = False
        self.activations = 0
        self.manifestations = 0
        self.t_activated: Optional[float] = None
        self.t_deactivated: Optional[float] = None
        self.last_sampled: Dict[str, Any] = {}

    # ------------------------------------------------------------------ hooks
    def apply(self, value, ctx: FaultContext):  # pragma: no cover - abstract
        raise NotImplementedError(f"{type(self).__name__}.apply is not implemented")

    def observe(self, value, ctx: FaultContext) -> None:
        return None

    def on_activate(self, ctx: FaultContext) -> Optional[Dict[str, Any]]:
        return None

    def on_deactivate(self, ctx: FaultContext) -> None:
        return None

    def reset(self) -> None:
        return None

    def manifests(self, before, after) -> bool:
        return changed(before, after)

    # ------------------------------------------------------------- parameters
    @classmethod
    def parameter_names(cls) -> Tuple[str, ...]:
        names = []
        for p in inspect.signature(cls.__init__).parameters.values():
            if p.name == "self" or p.name in cls._BASE_ARGS:
                continue
            if p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
                continue
            names.append(p.name)
        return tuple(names)

    def parameters(self) -> Dict[str, Any]:
        """The configured parameters as a plain dict (live values, not copies)."""
        return {n: getattr(self, n) for n in self.parameter_names() if hasattr(self, n)}

    def spec(self) -> Dict[str, Any]:
        return {
            "kind": type(self).__name__,
            "target": self.target,
            "name": self.name,
            "enabled": self.enabled,
            "max_activations": self.max_activations,
            "activation": self.activation.spec(),
            "duration": self.duration.spec(),
            "parameters": _to_plain(self.parameters()),
        }

    @classmethod
    def from_spec_kwargs(cls, kwargs, classes=None):
        params = kwargs.pop("parameters", {}) or {}
        return cls(kwargs.pop("target"), activation=kwargs.pop("activation", None),
                   duration=kwargs.pop("duration", None), name=kwargs.pop("name", None),
                   enabled=kwargs.pop("enabled", True), max_activations=kwargs.pop("max_activations", None),
                   **params)

    def __repr__(self):
        params = ", ".join(f"{k}={v!r}" for k, v in self.parameters().items())
        state = "active" if self.active else "dormant"
        return f"{type(self).__name__}({self.target!r}, {params}) [{self.name}, {state}]"
