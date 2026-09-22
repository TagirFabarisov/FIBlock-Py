"""A campaign: a set of faults injected together, with one seed, one clock and one event log."""
from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Optional, Union

from . import __version__
from ._rng import fault_rng, resolve_seed
from ._spec import MISSING, _to_plain
from .core import Fault, FaultContext, Outcome
from .events import ACTIVATED, DEACTIVATED, MANIFESTED, EventLog, FaultEvent

__all__ = ["Campaign"]

FaultRef = Union[str, Fault]


class Campaign:
    """Holds faults, drives their activation over time and records events.

    Typical use inside a simulation loop::

        campaign = Campaign([Bias("methane_sensor", 0.3, activation=At(120), duration=Fixed(30))], seed=42)
        for t in times:
            campaign.advance(t)                       # activations, expiries, triggers
            m = campaign.apply("methane_sensor", m)   # value as the sensor now reports it
            ...

    ``inject`` returns an :class:`Outcome` with the value and the names of the
    faults that altered it. Passing ``t`` to ``inject``/``apply`` advances the
    campaign automatically when ``t`` is later than the last advance.
    """

    def __init__(self, faults: Iterable[Fault] = (), *, seed=None, name: Optional[str] = None,
                 record_manifestations: bool = False, t0: float = 0.0):
        self.name = name
        self.record_manifestations = record_manifestations
        self.t0 = float(t0)
        self.faults: List[Fault] = []
        self._by_name: Dict[str, Fault] = {}
        self._seed: Optional[int] = None
        self.t = self.t0
        self.dt = 0.0
        self._started = False
        self.events = EventLog()
        for f in faults:
            self.add(f)
        self.reset(seed=seed, t0=self.t0)

    # ---------------------------------------------------------------- faults
    def add(self, fault: Fault) -> Fault:
        if fault._campaign is not None and fault._campaign is not self:
            raise ValueError(f"{fault!r} already belongs to another campaign")
        if fault.name is None:
            fault.name = f"{type(fault).__name__}@{fault.target}#{len(self.faults)}"
        if fault.name in self._by_name:
            raise ValueError(f"duplicate fault name {fault.name!r}")
        fault._campaign = self
        self.faults.append(fault)
        self._by_name[fault.name] = fault
        if self._seed is not None:
            self._seed_fault(fault)
            self._reset_fault(fault)
        return fault

    def get(self, ref: FaultRef) -> Fault:
        if isinstance(ref, Fault):
            return ref
        return self._by_name[ref]

    def targets(self) -> List[str]:
        return sorted({f.target for f in self.faults})

    def active(self, target: Optional[str] = None) -> List[Fault]:
        return [f for f in self.faults if f.active and (target is None or f.target == target)]

    @property
    def seed(self) -> Optional[int]:
        return self._seed

    # ----------------------------------------------------------------- reset
    def _seed_fault(self, fault: Fault):
        fault.rng, key = fault_rng(self._seed, fault.name)
        fault.seed_info = {"campaign_seed": self._seed, "name_key": key}

    def _ctx(self, fault: Fault, host=None) -> FaultContext:
        return FaultContext(t=self.t, dt=self.dt, rng=fault.rng, fault=fault, campaign=self, host=host)

    def _reset_fault(self, fault: Fault, host=None):
        fault._reset_state()
        fault.reset()
        fault.activation.reset(self._ctx(fault, host))

    def reset(self, seed=None, t0: Optional[float] = None, host=None) -> "Campaign":
        """Return every fault to dormant and restart the clock.

        ``seed=None`` keeps the current seed (an exact replay); pass a new seed
        for a different realisation. A campaign created without a seed draws
        one from the operating system and keeps it, so it is still replayable.
        """
        self._seed = resolve_seed(seed if seed is not None else self._seed)
        if t0 is not None:
            self.t0 = float(t0)
        self.t = self.t0
        self.dt = 0.0
        self._started = False
        self.events = EventLog()
        for f in self.faults:
            self._seed_fault(f)
        for f in self.faults:
            self._reset_fault(f, host)
        return self

    # --------------------------------------------------------------- driving
    def _eligible(self, f: Fault) -> bool:
        if not f.enabled or f.active:
            return False
        return f.max_activations is None or f.activations < f.max_activations

    def advance(self, t: float, host=None) -> "Campaign":
        """Move the clock to ``t``: expire, activate, and cascade triggered faults."""
        t = float(t)
        if self._started and t < self.t:
            raise ValueError(f"time must not go backwards (was {self.t}, got {t})")
        self.dt = (t - self.t) if self._started else 0.0
        self.t = t
        self._started = True
        for f in self.faults:
            if f.active and f.duration.expired(self._ctx(f, host)):
                self._deactivate(f, host, source="expired")
        self._cascade(host)
        return self

    def _cascade(self, host=None):
        """Poll dormant faults until no new activation appears (chained faults fire in the same step)."""
        guard = 0
        changed = True
        while changed and guard <= len(self.faults) + 1:
            changed = False
            guard += 1
            for f in self.faults:
                if not self._eligible(f):
                    continue
                sampled = f.activation.poll(self._ctx(f, host))
                if sampled is not None:
                    src = f"trigger:{sampled['trigger_source']}" if "trigger_source" in sampled else type(f.activation).__name__
                    self._activate(f, host, sampled, source=src)
                    changed = True

    def _activate(self, f: Fault, host, sampled: Optional[dict], source: str):
        ctx = self._ctx(f, host)
        f.active = True
        f.activations += 1
        f.t_activated = self.t
        f.t_deactivated = None
        merged = dict(sampled or {})
        merged.update(f.duration.start(ctx) or {})
        merged.update(f.on_activate(ctx) or {})
        f.last_sampled = merged
        self._emit(ACTIVATED, f, host, sampled=merged, source=source)

    def _deactivate(self, f: Fault, host, source: str):
        ctx = self._ctx(f, host)
        f.active = False
        f.t_deactivated = self.t
        f.on_deactivate(ctx)
        f.activation.on_deactivated(ctx)
        self._emit(DEACTIVATED, f, host, sampled={}, source=source)

    def _emit(self, kind: str, f: Fault, host, sampled: dict, source: str, record: bool = True):
        ev = FaultEvent(kind=kind, time=self.t, fault=f.name, fault_type=type(f).__name__, target=f.target,
                        parameters=_to_plain(f.parameters()), sampled=_to_plain(sampled), source=source,
                        seed=dict(f.seed_info) if f.seed_info else None)
        if record:
            self.events.append(ev)
        for g in self.faults:
            g.activation.notify(ev, self._ctx(g, host))
        return ev

    def activate(self, ref: FaultRef, t: Optional[float] = None, host=None, source: str = "manual") -> Fault:
        """Start a fault now, regardless of its activation model."""
        f = self.get(ref)
        if t is not None:
            self.advance(t, host)
        if not f.active:
            self._activate(f, host, {"activation_time": self.t}, source=source)
        return f

    def deactivate(self, ref: FaultRef, t: Optional[float] = None, host=None, source: str = "manual") -> Fault:
        """Stop a fault now, regardless of its duration model."""
        f = self.get(ref)
        if t is not None:
            self.advance(t, host)
        if f.active:
            self._deactivate(f, host, source=source)
        return f

    # ------------------------------------------------------------- injecting
    def inject(self, target: str, value, t: Optional[float] = None, host=None) -> Outcome:
        """Pass ``value`` through every active fault on ``target``."""
        if t is not None:
            t = float(t)
            if not self._started or t > self.t:
                self.advance(t, host)
            elif t < self.t:
                raise ValueError(f"inject at t={t} but campaign is already at t={self.t}")
        current = value
        manifested: List[str] = []
        applied: List[str] = []
        for f in self.faults:
            if f.target != target:
                continue
            ctx = self._ctx(f, host)
            f.observe(value, ctx)
            if not f.active or current is MISSING:
                continue
            out = f.apply(current, ctx)
            applied.append(f.name)
            if f.manifests(current, out):
                manifested.append(f.name)
                f.manifestations += 1
                self._emit(MANIFESTED, f, host, sampled={"before": _to_plain(current), "after": _to_plain(out)},
                           source="apply", record=self.record_manifestations)
                self._cascade(host)   # faults triggered by this manifestation start now
            current = out
        return Outcome(value=current, target=target, t=self.t, manifested=tuple(manifested), applied=tuple(applied))

    def apply(self, target: str, value, t: Optional[float] = None, host=None):
        """Like :meth:`inject` but returns only the value."""
        return self.inject(target, value, t, host).value

    # ----------------------------------------------------------------- specs
    def spec(self) -> Dict[str, Any]:
        """Everything needed to rebuild and replay this campaign, as plain data."""
        return {
            "fiblock": __version__,
            "name": self.name,
            "seed": self._seed,
            "t0": self.t0,
            "record_manifestations": self.record_manifestations,
            "faults": [f.spec() for f in self.faults],
        }

    @classmethod
    def from_spec(cls, spec: Dict[str, Any], classes: Optional[Dict[str, type]] = None) -> "Campaign":
        faults = [Fault.from_spec(s, classes) for s in spec["faults"]]
        return cls(faults, seed=spec.get("seed"), name=spec.get("name"),
                   record_manifestations=spec.get("record_manifestations", False), t0=spec.get("t0", 0.0))

    def to_json(self, **kw) -> str:
        return json.dumps(self.spec(), **kw)

    @classmethod
    def from_json(cls, text: str, classes: Optional[Dict[str, type]] = None) -> "Campaign":
        return cls.from_spec(json.loads(text), classes)

    def __repr__(self):
        return f"Campaign(name={self.name!r}, seed={self._seed}, t={self.t}, faults={len(self.faults)}, active={len(self.active())})"
