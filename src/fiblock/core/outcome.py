"""Result of passing one value through an injection point."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Tuple

from .missing import MISSING


@dataclass
class Outcome:
    value: Any                              # the value as it leaves the injection point
    t: float
    point: Optional[str] = None             # injection point name (None for a standalone injector)
    active: Tuple[str, ...] = ()            # injectors whose fault was active and applied
    data_error: bool = False                # value differs from the correct one (set by the campaign)
    caused_by: Tuple[str, ...] = ()         # injectors whose fault changed the value (set by the campaign)

    @property
    def missing(self) -> bool:
        return self.value is MISSING

    @property
    def clean(self) -> bool:
        return not self.data_error
