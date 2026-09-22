"""Data-error records: an observation, not a fault-injection event.

FIBlock injects *faults*. Whether an injected fault produces an *error* in the
data passing the injection point is a separate question: a packet-loss fault
active with probability 0.3 corrupts only some values, a freeze corrupts none
until a value arrives. The campaign compares the value before and after the
injection point and, when asked, records a :class:`DataErrorRecord` so that
the evidence is available (for example to train a model). The injection
mechanism itself never sees these records, and FIBlock makes no claim about
how a data error propagates beyond the injection point.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Tuple

import numpy as np

from ..core.missing import MISSING

DATA_ERROR = "data_error"


def is_data_error(before, after) -> bool:
    """True when the value leaving the injection point differs from the one entering it."""
    if before is MISSING or after is MISSING:
        return before is not after
    try:
        if isinstance(before, np.ndarray) or isinstance(after, np.ndarray):
            return not np.array_equal(before, after)
        return bool(before != after)
    except Exception:
        return True


@dataclass
class DataErrorRecord:
    time: float
    point: str
    caused_by: Tuple[str, ...]          # injectors whose active fault changed the value
    active: Tuple[str, ...]             # all injectors active at the point at that moment
    before: Any                         # the correct value
    after: Any                          # the erroneous value (or MISSING)
    kind: str = field(default=DATA_ERROR, init=False)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def __str__(self):
        return f"t={self.time:g} {self.kind:<13} {self.point}: {self.before!r} -> {self.after!r} caused by {list(self.caused_by)}"
