"""Random streams: one independent generator per injector, keyed by its name.

A campaign seed plus an injector name always yields the same stream, whatever
the order of injectors in the campaign and whatever other injectors exist.
Names are hashed with SHA-256 so the derivation is stable across Python
processes (the built-in ``hash`` is salted per process).
"""
from __future__ import annotations

import hashlib
from typing import Tuple

import numpy as np


def stable_key(name: str) -> int:
    """Map a name to a fixed 64-bit integer."""
    return int.from_bytes(hashlib.sha256(name.encode("utf-8")).digest()[:8], "little")


def resolve_seed(seed) -> int:
    """Turn ``None``/int/SeedSequence/Generator into a concrete integer seed.

    ``None`` draws fresh entropy from the operating system; the drawn value is
    returned so it can be stored and replayed.
    """
    if seed is None:
        return int(np.random.SeedSequence().entropy)  # type: ignore[arg-type]
    if isinstance(seed, np.random.SeedSequence):
        return int(seed.entropy)  # type: ignore[arg-type]
    if isinstance(seed, np.random.Generator):
        return int(seed.integers(0, 2**63 - 1))
    return int(seed)


def derived_rng(root_seed: int, name: str) -> Tuple[np.random.Generator, int]:
    """Independent generator for ``name`` under ``root_seed``; also returns the name key."""
    key = stable_key(name)
    return np.random.default_rng(np.random.SeedSequence([int(root_seed), key])), key
