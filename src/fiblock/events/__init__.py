"""Fault events: *when* a fault activates. One module per event.

Time is the host's time in the host's units; rates are per unit of that time.
Names follow the original FIBlock: ``Deterministic`` (a fixed time),
``FailureProbability`` (a probability per step, the only step-dependent
event), ``MeanTimeToFailure`` (a random time with a given mean),
``FailureTimeDistribution`` (a random time from any distribution),
``FailureRate`` (a hazard rate, constant or tabulated over time, the
descendant of the hand-drawn "manual distribution"). ``Never`` is an
addition: the event of an injector that only activates through its trigger
input or by hand. Chained faults are not an event: they use the injector's
trigger input (:class:`fiblock.core.Trigger`), which overrules the event, as
in the original block.
"""
from .deterministic import Deterministic
from .failure_probability import FailureProbability
from .failure_rate import FailureRate, TabulatedRate
from .failure_time_distribution import FailureTimeDistribution
from .mean_time_to_failure import MeanTimeToFailure
from .never import Never

__all__ = ["Deterministic", "FailureProbability", "MeanTimeToFailure", "FailureTimeDistribution", "FailureRate",
           "TabulatedRate", "Never"]
