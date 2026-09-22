"""Core: the fault-injection mechanism and the base classes it works with.

Nothing in this package knows a concrete fault type, fault event or fault
effect; those live in :mod:`fiblock.types`, :mod:`fiblock.events` and
:mod:`fiblock.effects`. Wiring several injectors together is done by
:mod:`fiblock.campaign`; collecting records by :mod:`fiblock.logger`.
"""
from .context import InjectionContext
from .fault_effect import FaultEffect
from .fault_event import FaultEvent
from .fault_type import FaultType
from .injector import FaultInjector
from .missing import MISSING
from .outcome import Outcome
from .records import ACTIVATION, DEACTIVATION, InjectionRecord, Recorder
from .rng import derived_rng, resolve_seed, stable_key
from .spec import Spec, from_plain, register, registry, to_plain
from .trigger import Trigger

__all__ = ["InjectionContext", "FaultEffect", "FaultEvent", "FaultType", "FaultInjector", "MISSING",
           "Outcome", "ACTIVATION", "DEACTIVATION", "InjectionRecord", "Recorder",
           "derived_rng", "resolve_seed", "stable_key", "Spec", "from_plain", "register", "registry", "to_plain", "Trigger"]
