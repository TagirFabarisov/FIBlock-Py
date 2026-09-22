"""Bit flips: random bits of the binary word are inverted (FIBlock "Bit flips", value = number of bits)."""
from __future__ import annotations

from typing import Optional

import numpy as np

from ..core import FaultType, register


@register
class BitFlip(FaultType):
    """Invert ``value`` randomly chosen bits of the binary representation.

    Floats use their IEEE-754 word (64 or 32 bits by dtype); Python ints use a
    two's-complement word of ``width`` bits (default 32); booleans are inverted;
    in a NumPy array one randomly chosen element is hit.
    """

    def __init__(self, value: int = 1, width: Optional[int] = None):
        self.value = value
        self.width = width

    def _flip_float(self, x, rng):
        arr = np.array(x)
        if arr.dtype == np.float32:
            u = arr.view(np.uint32)
            nbits = 32
        else:
            arr = arr.astype(np.float64)
            u = arr.view(np.uint64)
            nbits = 64
        for pos in rng.integers(0, nbits, size=self.value):
            u = u ^ (np.array(1, dtype=u.dtype) << np.array(int(pos), dtype=u.dtype))
        out = u.view(arr.dtype)
        return type(x)(out) if isinstance(x, (float, np.floating)) else out

    def _flip_int(self, x, rng):
        width = self.width or 32
        u = int(x) & ((1 << width) - 1)
        for pos in rng.integers(0, width, size=self.value):
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
