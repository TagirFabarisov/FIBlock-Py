"""The campaign: a wrapper that wires several injectors together.

The campaign is what the ``wrapper`` and the global injector map were in the
original FIBlock: it names injection points, hands each injector its seed, its
name and the recorder, drives all injectors on one clock, and delivers each
injector's activation records to the others' trigger inputs so that chained
faults work. It adds no fault semantics of its own; the mechanism is entirely
in :class:`fiblock.core.FaultInjector`. The one thing it observes on top is
whether the value leaving an injection point differs from the one entering
it, a *data error*, which it reports in the :class:`Outcome` and, if asked,
records for the logger.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Union

from .. import __version__
from ..core import FaultInjector, InjectionRecord, Outcome, from_plain, resolve_seed
from ..core.missing import MISSING
from ..logger import DataErrorRecord, InjectionLog, is_data_error

__all__ = ["Campaign"]

InjectorRef = Union[str, FaultInjector]


class Campaign:
    """Several injectors, one seed, one clock, one log.

    ::

        campaign = Campaign({
            "methane_sensor": FaultInjector(Bias(0.3), Deterministic(120.0), ConstantTime(30.0)),
            "bus": [FaultInjector(PacketLoss(0.5), FailureRate(0.02), ConstantTime(3.0)),
                    FaultInjector(Delay(1.0), Never(), ConstantTime(5.0), trigger=Trigger(by="PacketLoss@bus#1"))],
        }, seed=42)

        for t in times:
            campaign.advance(t)                          # expiries, events, chained triggers
            m = campaign.apply("methane_sensor", m)      # value as the sensor now reports it
            msg = campaign.inject("bus", msg)            # .value, .missing, .data_error, .caused_by

    Passing ``t`` to ``inject``/``apply`` advances the campaign when ``t`` is
    later than the last advance, so a host may also skip ``advance``.
    """

    def __init__(self, points: Optional[Mapping[str, Union[FaultInjector, Sequence[FaultInjector]]]] = None, *,
                 seed=None, name: Optional[str] = None, log: Optional[InjectionLog] = None,
                 record_data_errors: bool = False, t0: float = 0.0):
        self.name = name
        self.log = log if log is not None else InjectionLog()
        self.record_data_errors = record_data_errors
        self.t0 = float(t0)
        self.t = self.t0
        self._started = False
        self._seed: Optional[int] = None
        self._points: Dict[str, List[FaultInjector]] = {}
        self._by_name: Dict[str, FaultInjector] = {}
        self.injectors: List[FaultInjector] = []
        for point, injs in (points or {}).items():
            for inj in (injs if isinstance(injs, (list, tuple)) else [injs]):
                self.attach(point, inj)
        self.reset(seed=seed, t0=self.t0)

    # --------------------------------------------------------------- wiring
    def attach(self, point: str, injector: FaultInjector) -> FaultInjector:
        """Wire an injector to a named injection point."""
        if injector.point is not None and injector in self.injectors:
            raise ValueError(f"{injector!r} is already attached to point {injector.point!r}")
        if injector.name is None:
            injector.name = f"{type(injector.fault).__name__}@{point}#{len(self.injectors)}"
        if injector.name in self._by_name:
            raise ValueError(f"duplicate injector name {injector.name!r}")
        injector.point = str(point)
        injector.recorder = self.log
        self.injectors.append(injector)
        self._by_name[injector.name] = injector
        self._points.setdefault(str(point), []).append(injector)
        if self._seed is not None:
            injector.seed_from(self._seed, injector.name)
            injector.reset(t0=self.t)
        return injector

    def get(self, ref: InjectorRef) -> FaultInjector:
        return ref if isinstance(ref, FaultInjector) else self._by_name[ref]

    def points(self) -> List[str]:
        return list(self._points)

    def at(self, point: str) -> List[FaultInjector]:
        return list(self._points.get(point, []))

    def active(self, point: Optional[str] = None) -> List[FaultInjector]:
        return [i for i in self.injectors if i.error_flag and (point is None or i.point == point)]

    @property
    def seed(self) -> Optional[int]:
        return self._seed

    # ---------------------------------------------------------------- reset
    def reset(self, seed=None, t0: Optional[float] = None, host=None) -> "Campaign":
        """Return every injector to dormant and restart the clock.

        ``seed=None`` keeps the current seed (an exact replay); a new seed gives
        a new realisation. A campaign created without a seed draws one and
        keeps it, so it is still replayable.
        """
        self._seed = resolve_seed(seed if seed is not None else self._seed)
        if t0 is not None:
            self.t0 = float(t0)
        self.t = self.t0
        self._started = False
        self.log.clear()
        for inj in self.injectors:
            inj.seed_from(self._seed, inj.name)
        for inj in self.injectors:
            inj.reset(t0=self.t0, host=host)
        return self

    # -------------------------------------------------------------- driving
    def advance(self, t: float, host=None) -> "Campaign":
        """Move the clock to ``t`` on every injector, then resolve chained triggers."""
        t = float(t)
        if self._started and t < self.t:
            raise ValueError(f"time must not go backwards (was {self.t}, got {t})")
        self.t = t
        self._started = True
        produced: List[InjectionRecord] = []
        for inj in self.injectors:
            produced.extend(inj.step(t, host))
        self._dispatch(produced, host)
        return self

    def _dispatch(self, records: Iterable[InjectionRecord], host=None) -> None:
        """Deliver records to every trigger input, then poll until no chained activation is due."""
        pending = list(records)
        guard = 0
        while pending and guard <= 2 * len(self.injectors) + 2:
            guard += 1
            for rec in pending:
                for inj in self.injectors:
                    inj.notify(rec, host)
            pending = []
            for inj in self.injectors:
                rec = inj.poll(host)
                if rec is not None:
                    pending.append(rec)

    def activate(self, ref: InjectorRef, t: Optional[float] = None, host=None) -> FaultInjector:
        """Start an injector now, regardless of its fault event."""
        inj = self.get(ref)
        if t is not None:
            self.advance(t, host)
        if not inj.error_flag:
            self._dispatch([inj.activate(source="manual", host=host)], host)
        return inj

    def deactivate(self, ref: InjectorRef, t: Optional[float] = None, host=None) -> FaultInjector:
        """Stop an injector now, regardless of its fault effect."""
        inj = self.get(ref)
        if t is not None:
            self.advance(t, host)
        if inj.error_flag:
            self._dispatch([inj.deactivate(source="manual", host=host)], host)
        return inj

    # ------------------------------------------------------------ injecting
    def inject(self, point: str, value, t: Optional[float] = None, host=None) -> Outcome:
        """Pass ``value`` through every injector attached to ``point``, in attachment order."""
        if t is not None:
            t = float(t)
            if not self._started or t > self.t:
                self.advance(t, host)
            elif t < self.t:
                raise ValueError(f"inject at t={t} but campaign is already at t={self.t}")
        current = value
        active: List[str] = []
        caused_by: List[str] = []
        injectors = self._points.get(point, [])
        for i, inj in enumerate(injectors):
            out = inj.inject(current, host)
            active.extend(out.active)
            if out.active and is_data_error(current, out.value):
                caused_by.extend(out.active)
            current = out.value
            if current is MISSING:
                # remaining injectors still observe the correct value but cannot act on nothing
                for later in injectors[i + 1:]:
                    later.fault.observe(value, later.context(host))
                break
        data_error = is_data_error(value, current)
        if data_error and self.record_data_errors:
            self.log.record(DataErrorRecord(time=self.t, point=point, caused_by=tuple(caused_by), active=tuple(active),
                                            before=value, after=current))
        return Outcome(value=current, t=self.t, point=point, active=tuple(active), data_error=data_error,
                       caused_by=tuple(caused_by))

    def apply(self, point: str, value, t: Optional[float] = None, host=None):
        """Like :meth:`inject` but returns only the value."""
        return self.inject(point, value, t, host).value

    # ----------------------------------------------------------------- spec
    def spec(self) -> Dict[str, Any]:
        """Everything needed to rebuild and replay this campaign, as plain data."""
        return {"fiblock": __version__, "name": self.name, "seed": self._seed, "t0": self.t0,
                "record_data_errors": self.record_data_errors,
                "points": {p: [i.spec() for i in injs] for p, injs in self._points.items()}}

    @classmethod
    def from_spec(cls, spec: Dict[str, Any], classes: Optional[Dict[str, type]] = None) -> "Campaign":
        points = {p: [from_plain(s, classes) for s in specs] for p, specs in spec["points"].items()}
        return cls(points, seed=spec.get("seed"), name=spec.get("name"),
                   record_data_errors=spec.get("record_data_errors", False), t0=spec.get("t0", 0.0))

    def to_json(self, **kw) -> str:
        return json.dumps(self.spec(), **kw)

    @classmethod
    def from_json(cls, text: str, classes: Optional[Dict[str, type]] = None) -> "Campaign":
        return cls.from_spec(json.loads(text), classes)

    def __repr__(self):
        return (f"Campaign(name={self.name!r}, seed={self._seed}, t={self.t}, points={len(self._points)}, "
                f"injectors={len(self.injectors)}, active={len(self.active())})")
