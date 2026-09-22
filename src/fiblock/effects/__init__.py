"""Fault effects: *how long* the fault stays active (its exposure). One module per effect.

Names follow the original FIBlock: ``Once`` (a single step), ``ConstantTime``
(a fixed duration), ``InfiniteTime`` (until the end of the run),
``MeanTimeToRepair`` (a random duration with a given mean) and
``DurationDistribution`` (a random duration from any distribution: Weibull,
Gamma, Exponential, a mixture, ...). Explicit deactivation is always possible
through the injector or the campaign.
"""
from .constant_time import ConstantTime
from .duration_distribution import DurationDistribution
from .infinite_time import InfiniteTime
from .mean_time_to_repair import MeanTimeToRepair
from .once import Once

__all__ = ["Once", "ConstantTime", "InfiniteTime", "MeanTimeToRepair", "DurationDistribution"]
