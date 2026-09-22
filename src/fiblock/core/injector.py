"""The fault injector: the mechanism that combines a fault type, a fault event
and a fault effect at one injection point.

This is the Python counterpart of one FIBlock block instance. It owns the
run-time state (the error flag, activation times, counters), polls the fault
event while dormant, polls the fault effect while active, applies the fault
type to injected values, and reports records to a recorder. It knows nothing
about concrete fault types, events or effects beyond their base interfaces,
and nothing about other injectors: wiring several injectors together (chained
faults, injection point names, one seed for all) is the campaign's job.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

from .context import InjectionContext
from .fault_effect import FaultEffect
from .fault_event import FaultEvent
from .fault_type import FaultType
from .missing import MISSING
from .outcome import Outcome
from .records import ACTIVATION, DEACTIVATION, InjectionRecord, Recorder
from .rng import derived_rng
from .spec import Spec, register, to_plain
from .trigger import Trigger


@register
class FaultInjector(Spec):
    """One injection point: ``fault`` (what) + ``event`` (when) + ``effect`` (how long),
    plus an optional ``trigger`` input that overrules the event (chained faults).

    Standalone use::

        inj = FaultInjector(Bias(0.3), Deterministic(120.0), ConstantTime(30.0), seed=1)
        for t in times:
            inj.step(t)
            reading = inj.inject(reading).value

    Inside a :class:`fiblock.Campaign` the campaign calls ``step``/``inject``
    and supplies the seed, the name, the recorder and the chaining.
    """

    def __init__(self, fault: FaultType, event: FaultEvent, effect: FaultEffect, *,
                 trigger: Optional[Trigger] = None, name: Optional[str] = None, enabled: bool = True,
                 max_activations: Optional[int] = None, seed=None, recorder: Optional[Recorder] = None):
        self.fault = fault
        self.event = event
        self.effect = effect
        self.trigger = trigger
        self.name = name
        self.enabled = bool(enabled)
        self.max_activations = max_activations
        self.recorder = recorder
        self.point: Optional[str] = None
        self.rng: Optional[np.random.Generator] = None
        self.seed_info: Optional[Dict[str, int]] = None
        self.t = 0.0
        self.dt = 0.0
        self._started = False
        self._reset_state()
        if seed is not None:
            self.reset(seed=seed)

    # ------------------------------------------------------------------ state
    def _reset_state(self):
        self.error_flag = False                 # FIBlock's Fflag: the fault is active
        self.activation_count = 0
        self.t_activated: Optional[float] = None
        self.t_deactivated: Optional[float] = None
        self.injection_points: List[float] = []  # FIBlock's FInjectionPoints: activation times
        self.last_sampled: Dict[str, Any] = {}

    @property
    def active(self) -> bool:
        return self.error_flag

    def eligible(self) -> bool:
        if not self.enabled or self.error_flag:
            return False
        return self.max_activations is None or self.activation_count < self.max_activations

    def context(self, host=None) -> InjectionContext:
        return InjectionContext(t=self.t, dt=self.dt, rng=self.rng, injector=self, host=host)

    # ------------------------------------------------------------------ seeds
    def seed_from(self, root_seed: int, key: Optional[str] = None) -> None:
        """Derive this injector's stream from a root seed and a stable key (its name)."""
        self.rng, name_key = derived_rng(root_seed, key if key is not None else (self.name or ""))
        self.seed_info = {"root_seed": int(root_seed), "name_key": name_key}

    def reset(self, seed=None, t0: float = 0.0, host=None) -> "FaultInjector":
        if seed is not None:
            self.rng = np.random.default_rng(int(seed))
            self.seed_info = {"seed": int(seed)}
        if self.rng is None:
            raise ValueError("injector has no random stream: pass seed=... or attach it to a Campaign")
        self.t = float(t0)
        self.dt = 0.0
        self._started = False
        self._reset_state()
        self.fault.reset()
        self.event.reset(self.context(host))
        if self.trigger is not None:
            self.trigger.reset(self.context(host))
        return self

    # --------------------------------------------------------------- stepping
    def step(self, t: float, host=None) -> List[InjectionRecord]:
        """Move the clock to ``t``: end an expired effect, then poll the event."""
        t = float(t)
        if self.rng is None:
            raise ValueError("injector has no random stream: pass seed=... or attach it to a Campaign")
        if self._started and t < self.t:
            raise ValueError(f"time must not go backwards (was {self.t}, got {t})")
        self.dt = (t - self.t) if self._started else 0.0
        self.t = t
        self._started = True
        records: List[InjectionRecord] = []
        if self.error_flag and self.effect.expired(self.context(host)):
            records.append(self.deactivate(source="expired", host=host))
        rec = self.poll(host)
        if rec is not None:
            records.append(rec)
        return records

    def poll(self, host=None) -> Optional[InjectionRecord]:
        """Ask the trigger input, then the fault event, whether to activate now (no clock change)."""
        if not self.eligible():
            return None
        ctx = self.context(host)
        if self.trigger is not None:
            sampled = self.trigger.poll(ctx)
            if sampled is not None:
                return self.activate(sampled=sampled, source=f"trigger:{sampled['trigger_source']}", host=host)
        sampled = self.event.poll(ctx)
        if sampled is None:
            return None
        return self.activate(sampled=sampled, source=type(self.event).__name__, host=host)

    def activate(self, sampled: Optional[dict] = None, source: str = "manual", host=None) -> InjectionRecord:
        """Raise the error flag now (an activation record is produced)."""
        ctx = self.context(host)
        self.error_flag = True
        self.activation_count += 1
        self.t_activated = self.t
        self.t_deactivated = None
        self.injection_points.append(self.t)
        merged = {"activation_time": self.t}
        merged.update(sampled or {})
        merged.update(self.effect.start(ctx) or {})
        merged.update(self.fault.on_activate(ctx) or {})
        self.last_sampled = merged
        return self._record(ACTIVATION, merged, source)

    def deactivate(self, source: str = "manual", host=None) -> InjectionRecord:
        """Lower the error flag now (a deactivation record is produced)."""
        ctx = self.context(host)
        self.error_flag = False
        self.t_deactivated = self.t
        self.fault.on_deactivate(ctx)
        self.event.on_deactivated(ctx)
        return self._record(DEACTIVATION, {}, source)

    def notify(self, record: InjectionRecord, host=None) -> None:
        """Deliver a campaign record to the trigger input (chained faults listen here)."""
        if self.trigger is not None:
            self.trigger.notify(record, self.context(host))

    # -------------------------------------------------------------- injecting
    def inject(self, value, host=None) -> Outcome:
        """Pass a value through this injection point: the fault type is applied while the error flag is up."""
        ctx = self.context(host)
        self.fault.observe(value, ctx)
        if not self.error_flag or value is MISSING:
            return Outcome(value=value, t=self.t, point=self.point)
        out = self.fault.apply(value, ctx)
        return Outcome(value=out, t=self.t, point=self.point, active=(self.name or type(self.fault).__name__,))

    # ---------------------------------------------------------------- records
    def _record(self, kind: str, sampled: dict, source: str) -> InjectionRecord:
        rec = InjectionRecord(kind=kind, time=self.t, injector=self.name or type(self.fault).__name__,
                              fault_type=type(self.fault).__name__, point=self.point,
                              parameters=to_plain(self.fault.parameters()), sampled=to_plain(sampled),
                              source=source, seed=dict(self.seed_info) if self.seed_info else None)
        if self.recorder is not None:
            self.recorder.record(rec)
        return rec

    # ------------------------------------------------------------------- spec
    def spec(self) -> Dict[str, Any]:
        return {"kind": "FaultInjector", "name": self.name, "enabled": self.enabled,
                "max_activations": self.max_activations, "fault": self.fault.spec(), "event": self.event.spec(), "effect": self.effect.spec(),
                "trigger": None if self.trigger is None else self.trigger.spec()}

    @classmethod
    def from_spec_kwargs(cls, kwargs, classes=None):
        return cls(kwargs.pop("fault"), kwargs.pop("event"), kwargs.pop("effect"), **kwargs)

    def __repr__(self):
        state = "active" if self.error_flag else "dormant"
        trig = f", trigger={self.trigger!r}" if self.trigger is not None else ""
        return f"FaultInjector({self.fault!r}, {self.event!r}, {self.effect!r}{trig}) [{self.name}, {state}]"
