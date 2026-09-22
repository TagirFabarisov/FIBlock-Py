"""Fault types: *what* the error looks like. One module per type.

Numeric fault types (Bias, Drift, Noise, Gain, Freeze, StuckAt, BitFlip)
transform the value; delivery fault types (Delay, PacketLoss) may return
:data:`fiblock.MISSING`, meaning nothing arrived. What a receiver does with a
missing value is the receiver's decision.

By FIBlock convention the main parameter of every type is its ``value`` (the
"fault value"): the bias, the drift slope, the noise amplitude, the number of
bits, the delay, the drop probability. To add a type, copy one of these
modules, subclass :class:`fiblock.FaultType` and implement ``apply``.
"""
from .bias import Bias
from .bit_flip import BitFlip
from .delay import Delay
from .drift import Drift
from .freeze import Freeze
from .gain import Gain
from .noise import Noise
from .packet_loss import PacketLoss
from .stuck_at import StuckAt

__all__ = ["Bias", "Drift", "Noise", "Gain", "Freeze", "StuckAt", "BitFlip", "Delay", "PacketLoss"]
