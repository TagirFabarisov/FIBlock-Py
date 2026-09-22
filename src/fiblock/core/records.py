"""What the injection mechanism reports: one record per fault activation and
per fault deactivation. Collecting, filtering and exporting records is the
logger's job (:mod:`fiblock.logger`); the mechanism only hands them to a
``Recorder``. Whether an injected fault produced an erroneous value is not
the mechanism's concern; see :mod:`fiblock.logger.data_error`."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional

ACTIVATION = "activation"           # the fault became active (an injection point in FIBlock terms)
DEACTIVATION = "deactivation"       # the fault effect ended


@dataclass
class InjectionRecord:
    kind: str
    time: float
    injector: str                                   # injector name (unique within a campaign)
    fault_type: str                                 # class name of the fault type
    point: Optional[str] = None                     # injection point the injector is attached to
    parameters: Dict[str, Any] = field(default_factory=dict)   # configured fault parameters
    sampled: Dict[str, Any] = field(default_factory=dict)      # values drawn at run time
    source: Optional[str] = None                    # cause: event class, "chained:<injector>", "manual", "expired", ...
    seed: Optional[Dict[str, int]] = None           # seed provenance

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def __str__(self):
        where = f" on {self.point}" if self.point else ""
        extra = f" sampled={self.sampled}" if self.sampled else ""
        return f"t={self.time:g} {self.kind:<13} {self.injector} ({self.fault_type}{where}) via {self.source}{extra}"


class Recorder:
    """Anything with ``record(InjectionRecord)``; :class:`fiblock.logger.InjectionLog` is one."""

    def record(self, record: InjectionRecord) -> None:  # pragma: no cover - interface
        raise NotImplementedError
