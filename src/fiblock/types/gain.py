"""Gain fault: the value is multiplied by a factor (a multiplicative fault).

In the sensor-fault literature this is the *gain* or *scaling* fault
(Isermann's multiplicative fault, as opposed to the additive offset); in the
actuator and component literature it is *loss of effectiveness*: a pump that
delivers 60 % of its nominal flow, an actuator that applies 80 % of the
commanded force.
"""
from __future__ import annotations

from ..core import FaultType, register


@register
class Gain(FaultType):
    """Multiply by ``value`` (``0.6``: the component works at 60 % effectiveness)."""

    def __init__(self, value: float):
        self.value = value

    def apply(self, value, ctx):
        return value * self.value
