"""The injection log: collects fault-injection records and data-error records."""
from __future__ import annotations

import json
from typing import Dict, Optional

from ..core.records import InjectionRecord, Recorder
from .data_error import DATA_ERROR, DataErrorRecord


class InjectionLog(list, Recorder):
    """A list of :class:`InjectionRecord` (fault activations and deactivations)
    and :class:`DataErrorRecord` (observed data errors) that also serves as a
    ``Recorder``."""

    def record(self, record) -> None:
        self.append(record)

    def filter(self, kind: Optional[str] = None, injector: Optional[str] = None,
               point: Optional[str] = None) -> "InjectionLog":
        out = InjectionLog()
        for r in self:
            if kind is not None and r.kind != kind:
                continue
            if point is not None and r.point != point:
                continue
            if injector is not None:
                if isinstance(r, DataErrorRecord):
                    if injector not in r.caused_by:
                        continue
                elif r.injector != injector:
                    continue
            out.append(r)
        return out

    def faults(self) -> "InjectionLog":
        """Only the fault-injection records (activations and deactivations)."""
        return InjectionLog(r for r in self if isinstance(r, InjectionRecord))

    def data_errors(self) -> "InjectionLog":
        """Only the data-error records."""
        return InjectionLog(r for r in self if isinstance(r, DataErrorRecord))

    def counts(self) -> Dict[str, int]:
        c: Dict[str, int] = {}
        for r in self:
            c[r.kind] = c.get(r.kind, 0) + 1
        return c

    def to_dicts(self):
        return [r.to_dict() for r in self]

    def to_json(self, **kw) -> str:
        return json.dumps(self.to_dicts(), **kw)
