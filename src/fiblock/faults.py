"""Built-in fault types.

Numeric faults (Bias, Drift, Noise, Scale, Freeze, StuckAt, BitFlip) transform
the value passing through the injection point. Timing and delivery faults
(Delay, PacketLoss) may return :data:`MISSING`, meaning nothing arrived; what
the receiver does with a missing value (hold the last one, substitute, switch
mode) is the receiver's decision, not the fault's.

All parameters are ordinary attributes: ``fault.magnitude = 0.2`` is the
supported way for an external program to set them.
"""
from __future__ import annotations

from typing import Any, List, Optional, Tuple

import numpy as np

from ._spec import MISSING, register
from .core import Fault, FaultContext
from .distributions import Distribution, Normal, as_distribution

__all__ = ["Bias", "Drift", "Noise", "Scale", "Freeze", "StuckAt", "BitFlip", "Delay", "PacketLoss"]


@register
class Bias(Fault):
    """Add a constant offset (``relative=True``: multiply by ``1 + magnitude``)."""

    def __init__(self, target, magnitude: float, relative: bool = False, **kw):
        super().__init__(target, **kw)
        self.magnitude = magnitude
        self.relative = relative

    def apply(self, value, ctx):
        if self.relative:
            return value * (1.0 + self.magnitude)
        return value + self.magnitude


@register
class Drift(Fault):
    """Offset growing linearly with time since activation: ``rate * elapsed``
    (``relative=True``: multiply by ``1 + rate * elapsed``)."""

    def __init__(self, target, rate: float, relative: bool = False, **kw):
        super().__init__(target, **kw)
        self.rate = rate
        self.relative = relative

    def apply(self, value, ctx):
        e = ctx.elapsed or 0.0
        if self.relative:
            return value * (1.0 + self.rate * e)
        return value + self.rate * e


@register
class Noise(Fault):
    """Add random noise: ``amplitude * sample`` from ``distribution`` (standard normal
    by default). ``relative=True`` scales the noise by the value itself, as in the
    original FIBlock's percentage noise (use ``distribution=Uniform(-1, 1)`` for that)."""

    def __init__(self, target, amplitude: float, relative: bool = False, distribution: Any = None, **kw):
        super().__init__(target, **kw)
        self.amplitude = amplitude
        self.relative = relative
        self.distribution = as_distribution(distribution) if distribution is not None else Normal(0.0, 1.0)

    def _draw(self, value, rng):
        if isinstance(value, np.ndarray):
            flat = np.array([self.distribution.sample(rng) for _ in range(value.size)], dtype=float)
            return flat.reshape(value.shape)
        return self.distribution.sample(rng)

    def apply(self, value, ctx):
        s = self._draw(value, ctx.rng)
        if self.relative:
            return value * (1.0 + self.amplitude * s)
        return value + self.amplitude * s


@register
class Scale(Fault):
    """Multiply by ``factor`` (e.g. a pump delivering 60 % of nominal capacity)."""

    def __init__(self, target, factor: float, **kw):
        super().__init__(target, **kw)
        self.factor = factor

    def apply(self, value, ctx):
        return value * self.factor


@register
class Freeze(Fault):
    """Hold the last correct value seen before activation (sensor freeze / stuck-at-current)."""

    def __init__(self, target, **kw):
        super().__init__(target, **kw)
        self._last = MISSING
        self._frozen = MISSING

    def reset(self):
        self._last = MISSING
        self._frozen = MISSING

    def observe(self, value, ctx):
        if not self.active:
            self._last = value

    def on_activate(self, ctx):
        self._frozen = self._last
        return {"frozen_value": None if self._frozen is MISSING else self._frozen}

    def apply(self, value, ctx):
        if self._frozen is MISSING:   # nothing observed yet: cannot freeze
            return value
        return self._frozen


@register
class StuckAt(Fault):
    """Replace by a fixed ``value`` (stuck-at-0, stuck-at-max, ...)."""

    def __init__(self, target, value: Any, **kw):
        super().__init__(target, **kw)
        self.value = value

    def apply(self, value, ctx):
        return self.value


@register
class BitFlip(Fault):
    """Invert ``bits`` randomly chosen bits of the binary representation.

    Floats use their IEEE-754 word (64 or 32 bits by dtype); Python ints use a
    two's-complement word of ``width`` bits (default 32); booleans are inverted;
    for a NumPy array one randomly chosen element is hit.
    """

    def __init__(self, target, bits: int = 1, width: Optional[int] = None, **kw):
        super().__init__(target, **kw)
        self.bits = bits
        self.width = width

    def _flip_float(self, x, rng):
        arr = np.array(x)
        if arr.dtype == np.float32:
            u = arr.view(np.uint32); nbits = 32
        else:
            arr = arr.astype(np.float64); u = arr.view(np.uint64); nbits = 64
        for pos in rng.integers(0, nbits, size=self.bits):
            u = u ^ np.array(1, dtype=u.dtype) << np.array(int(pos), dtype=u.dtype)
        out = u.view(arr.dtype)
        return type(x)(out) if isinstance(x, (float, np.floating)) else out

    def _flip_int(self, x, rng):
        width = self.width or 32
        mask = (1 << width) - 1
        u = int(x) & mask
        for pos in rng.integers(0, width, size=self.bits):
            u ^= 1 << int(pos)
        if u >= 1 << (width - 1):
            u -= 1 << width
        return type(x)(u) if isinstance(x, np.integer) else int(u)

    def _flip_scalar(self, x, rng):
        if isinstance(x, (bool, np.bool_)):
            return not x
        if isinstance(x, (int, np.integer)):
            return self._flip_int(x, rng)
        if isinstance(x, (float, np.floating)):
            return self._flip_float(x, rng)
        raise TypeError(f"BitFlip cannot flip bits of {type(x).__name__}")

    def apply(self, value, ctx):
        if isinstance(value, np.ndarray):
            out = value.copy().reshape(-1)
            i = int(ctx.rng.integers(0, out.size))
            out[i] = self._flip_scalar(out[i], ctx.rng)
            return out.reshape(value.shape)
        return self._flip_scalar(value, ctx.rng)


@register
class Delay(Fault):
    """Values arrive late by ``delay`` time units.

    While active, each value passed in is queued with its time stamp and
    delivered when the host's time has advanced by ``delay``. Until the first
    late value is due, nothing arrives: the result is :data:`MISSING`, or, with
    ``gap="hold"``, the last correct value seen before activation. On
    deactivation the queue is dropped and values arrive on time again.
    ``delay`` may be a distribution; it is then sampled at each activation.
    """

    def __init__(self, target, delay: Any, gap: str = "missing", **kw):
        super().__init__(target, **kw)
        if gap not in ("missing", "hold"):
            raise ValueError("Delay.gap must be 'missing' or 'hold'")
        self.delay = delay
        self.gap = gap
        self._queue: List[Tuple[float, Any]] = []
        self._current_delay: Optional[float] = None
        self._last_before = MISSING
        self._last_delivered = MISSING

    def reset(self):
        self._queue = []
        self._current_delay = None
        self._last_before = MISSING
        self._last_delivered = MISSING

    def observe(self, value, ctx):
        if not self.active:
            self._last_before = value

    def on_activate(self, ctx):
        self._current_delay = as_distribution(self.delay).sample(ctx.rng)
        self._queue = []
        self._last_delivered = MISSING
        return {"delay": self._current_delay}

    def on_deactivate(self, ctx):
        self._queue = []

    def apply(self, value, ctx):
        self._queue.append((ctx.t, value))
        due_time = ctx.t - self._current_delay
        delivered = MISSING
        keep = []
        for (ts, v) in self._queue:
            if ts <= due_time:
                delivered = v
            else:
                keep.append((ts, v))
        if delivered is not MISSING:
            self._queue = keep
            self._last_delivered = delivered
            return delivered
        if self._last_delivered is not MISSING:
            return self._last_delivered   # between deliveries: the last late value stays visible
        if self.gap == "hold":
            return value if self._last_before is MISSING else self._last_before
        return MISSING

    def manifests(self, before, after):
        return before is not after and super().manifests(before, after)


@register
class PacketLoss(Fault):
    """Each value is dropped with ``probability`` (1.0 = every value while active).

    A dropped value becomes :data:`MISSING`, or ``substitute`` if one is given
    (the original FIBlock replaced dropped packets by a fixed value).
    """

    def __init__(self, target, probability: float = 1.0, substitute: Any = MISSING, **kw):
        super().__init__(target, **kw)
        self.probability = probability
        self.substitute = substitute

    def apply(self, value, ctx):
        if self.probability >= 1.0 or ctx.rng.random() < self.probability:
            return self.substitute
        return value
