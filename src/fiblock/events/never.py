"""Never: the fault only activates on an explicit ``activate`` call."""
from __future__ import annotations

from dataclasses import dataclass

from ..core import FaultEvent, register


@register
@dataclass
class Never(FaultEvent):
    """Never activates by itself."""
