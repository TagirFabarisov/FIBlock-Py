"""FIBlock: model-based fault injection for cyber-physical systems, in Python.

    from fiblock import Bias, Drift, Noise, Freeze, Delay, PacketLoss, Campaign, At, Fixed

A fault is attached to a named injection point and described by three
independent choices: what the error looks like (the fault class and its
parameters), when it activates (an activation model) and how long it lasts
(a duration model). A :class:`Campaign` groups faults, seeds them, drives them
over the host's clock and records every activation, deactivation and, if
asked, every manifested error.

FIBlock is simulator-agnostic: the host passes values through
``campaign.apply(target, value, t)`` and decides what to do with the result.
"""
__version__ = "0.1.0"

from ._spec import MISSING, register, registry  # noqa: E402
from .core import Fault, FaultContext, Outcome, changed  # noqa: E402
from .events import ACTIVATED, DEACTIVATED, MANIFESTED, EventLog, FaultEvent  # noqa: E402
from .distributions import (  # noqa: E402
    Distribution, Constant, Uniform, Normal, LogNormal, Exponential, Weibull, Gamma, Choice, Mixture,
    Empirical, FromCallable, Scipy, as_distribution,
)
from .activation import (  # noqa: E402
    Activation, Immediately, At, Never, SampledTime, Rate, TabulatedRate, PerStep, When, Triggered,
)
from .duration import Duration, Permanent, Once, Fixed, SampledDuration, Until  # noqa: E402
from .faults import Bias, Drift, Noise, Scale, Freeze, StuckAt, BitFlip, Delay, PacketLoss  # noqa: E402
from .campaign import Campaign  # noqa: E402

__all__ = [
    "__version__", "MISSING", "register", "registry",
    "Fault", "FaultContext", "Outcome", "changed",
    "ACTIVATED", "DEACTIVATED", "MANIFESTED", "EventLog", "FaultEvent",
    "Distribution", "Constant", "Uniform", "Normal", "LogNormal", "Exponential", "Weibull", "Gamma",
    "Choice", "Mixture", "Empirical", "FromCallable", "Scipy", "as_distribution",
    "Activation", "Immediately", "At", "Never", "SampledTime", "Rate", "TabulatedRate", "PerStep", "When", "Triggered",
    "Duration", "Permanent", "Once", "Fixed", "SampledDuration", "Until",
    "Bias", "Drift", "Noise", "Scale", "Freeze", "StuckAt", "BitFlip", "Delay", "PacketLoss",
    "Campaign",
]
