"""Seed derivation: one independent random stream per fault, keyed by the fault's name.

A campaign seed plus a fault name always yields the same stream, whatever the
order of faults in the campaign and whatever other faults exist. Names are
hashed with SHA-256 so the derivation is stable across Python processes
(Python's built-in ``hash`` is salted per process and cannot be used).
"""
from __future__ import annotations

import hashlib
from typing import Optional, Tuple

import numpy as np


def stable_key(name: str) -> int:
    """Map a fault name to a fixed 64-bit integer."""
    digest = hashlib.sha256(name.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "little")


def resolve_seed(seed) -> int:
    """Turn ``None``/int/SeedSequence/Generator into a concrete integer seed.

    ``None`` draws fresh entropy from the operating system; the drawn value is
    returned so it can be stored and replayed.
    """
    if seed is None:
        entropy = np.random.SeedSequence().entropy
        return int(entropy)  # type: ignore[arg-type]
    if isinstance(seed, np.random.SeedSequence):
        return int(seed.entropy)  # type: ignore[arg-type]
    if isinstance(seed, np.random.Generator):
        # Derive a concrete seed from the generator so the campaign stays replayable.
        return int(seed.integers(0, 2**63 - 1))
    return int(seed)


def fault_rng(campaign_seed: int, name: str) -> Tuple[np.random.Generator, int]:
    """Independent generator for one fault; also returns the name key used."""
    key = stable_key(name)
    seq = np.random.SeedSequence([int(campaign_seed), key])
    return np.random.default_rng(seq), key
