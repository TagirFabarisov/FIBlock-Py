"""What a fault type, fault event or fault effect sees when it is called."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import numpy as np


@dataclass
class InjectionContext:
    """Passed to every hook of a fault type, fault event and fault effect.

    ``t`` is the host's current time in the host's own units and ``dt`` the
    time since the previous step (0 on the first). ``rng`` is the injector's
    own seeded generator. ``injector`` gives access to the injector's state
    (``error_flag``, ``t_activated`` ...). ``host`` is whatever object the host
    passed along, for conditions that need to look at simulator state.
    """
    t: float
    dt: float
    rng: np.random.Generator
    injector: Any
    host: Any = None

    @property
    def fault(self):
        return self.injector.fault

    @property
    def t_activated(self) -> Optional[float]:
        return self.injector.t_activated

    @property
    def elapsed(self) -> Optional[float]:
        """Time since the current activation, or None while the fault is dormant."""
        if self.injector.t_activated is None:
            return None
        return self.t - self.injector.t_activated
