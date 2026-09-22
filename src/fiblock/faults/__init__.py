"""Built-in fault types, one per module.

Numeric faults (Bias, Drift, Noise, Scale, Freeze, StuckAt, BitFlip) transform
the value passing through the injection point. Timing and delivery faults
(Delay, PacketLoss) may return :data:`fiblock.MISSING`, meaning nothing
arrived; what the receiver does with a missing value is the receiver's
decision, not the fault's.

To add a fault type, copy one of these modules, subclass :class:`fiblock.Fault`
and implement ``apply``. All parameters are ordinary attributes: an external
program sets them with plain assignment, e.g. ``fault.magnitude = 0.2``.
"""
from .bias import Bias
from .bit_flip import BitFlip
from .delay import Delay
from .drift import Drift
from .freeze import Freeze
from .noise import Noise
from .packet_loss import PacketLoss
from .scale import Scale
from .stuck_at import StuckAt

__all__ = ["Bias", "Drift", "Noise", "Scale", "Freeze", "StuckAt", "BitFlip", "Delay", "PacketLoss"]
