"""A distribution is any object with ``sample(rng) -> float``."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import numpy as np

from ..core.spec import Spec


class Distribution(Spec):
    def sample(self, rng: np.random.Generator) -> float:  # pragma: no cover - abstract
        raise NotImplementedError


@dataclass
class FromCallable(Distribution):
    """Wrap any ``fn(rng) -> float``. Not restorable from a spec."""
    fn: Callable[[np.random.Generator], float]

    def sample(self, rng):
        return float(self.fn(rng))

    def spec(self):
        return {"kind": "FromCallable", "repr": repr(self.fn)}


@dataclass
class Scipy(Distribution):
    """Adapter for a SciPy frozen distribution (anything with ``rvs``)."""
    frozen: Any

    def sample(self, rng):
        return float(self.frozen.rvs(random_state=rng))

    def spec(self):
        return {"kind": "Scipy", "repr": repr(self.frozen)}


def as_distribution(x) -> Distribution:
    """Coerce a number (constant), callable, SciPy object or Distribution into a Distribution."""
    from .continuous import Constant
    if isinstance(x, Distribution):
        return x
    if isinstance(x, (int, float, np.integer, np.floating)) and not isinstance(x, bool):
        return Constant(float(x))
    if hasattr(x, "rvs"):
        return Scipy(x)
    if callable(x):
        return FromCallable(x)
    raise TypeError(f"cannot interpret {x!r} as a distribution")
