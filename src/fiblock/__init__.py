"""FIBlock: model-based fault injection for cyber-physical systems, in Python.

    from fiblock import Bias, Drift, Noise, Freeze, Delay, PacketLoss

A fault injector combines three independent choices, as in the original
FIBlock block: a **fault type** (what the error looks like, with its fault
value), a **fault event** (when it activates) and a **fault effect** (how long
it lasts), plus a **trigger** input that overrules the event so that one
injector can force another (chained faults). FIBlock injects faults; whether
a fault produces an erroneous value is reported separately as a *data error*,
and how that error propagates is not FIBlock's business. A **campaign** wires injectors to named injection points under one
seed and one clock; the **logger** collects the records they produce.

Packages: ``core`` (mechanism and base classes), ``types``, ``events``,
``effects``, ``distributions``, ``campaign``, ``logger``.
"""
__version__ = "0.2.0"

from .core import (  # noqa: E402
    MISSING, ACTIVATION, DEACTIVATION, FaultEffect, FaultEvent, FaultInjector, FaultType,
    InjectionContext, InjectionRecord, Outcome, Recorder, Trigger, register, registry,
)
from .distributions import (  # noqa: E402
    Distribution, Constant, Uniform, Normal, LogNormal, Exponential, Weibull, Gamma, Choice, Empirical, Mixture,
    FromCallable, Scipy, as_distribution,
)
from .types import Bias, BitFlip, Delay, Drift, Freeze, Gain, Noise, PacketLoss, StuckAt  # noqa: E402
from .events import (  # noqa: E402
    Deterministic, FailureProbability, FailureRate, FailureTimeDistribution, MeanTimeToFailure, Never, TabulatedRate,
)
from .effects import ConstantTime, DurationDistribution, InfiniteTime, MeanTimeToRepair, Once  # noqa: E402
from .logger import DATA_ERROR, DataErrorRecord, InjectionLog  # noqa: E402
from .campaign import Campaign  # noqa: E402

__all__ = [
    "__version__",
    # core
    "MISSING", "ACTIVATION", "DEACTIVATION", "FaultEffect", "FaultEvent", "FaultInjector",
    "FaultType", "InjectionContext", "InjectionRecord", "Outcome", "Recorder", "Trigger", "register", "registry",
    # distributions
    "Distribution", "Constant", "Uniform", "Normal", "LogNormal", "Exponential", "Weibull", "Gamma", "Choice",
    "Empirical", "Mixture", "FromCallable", "Scipy", "as_distribution",
    # fault types
    "Bias", "BitFlip", "Delay", "Drift", "Freeze", "Gain", "Noise", "PacketLoss", "StuckAt",
    # fault events
    "Deterministic", "FailureProbability", "FailureRate", "FailureTimeDistribution",
    "MeanTimeToFailure", "Never", "TabulatedRate",
    # fault effects
    "ConstantTime", "DurationDistribution", "InfiniteTime", "MeanTimeToRepair", "Once",
    # logger and campaign
    "InjectionLog", "DataErrorRecord", "DATA_ERROR", "Campaign",
]
