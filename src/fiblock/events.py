"""Event records: what happened, when, to which fault, with which parameters."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional

ACTIVATED = "activated"
DEACTIVATED = "deactivated"
MANIFESTED = "manifested"


@dataclass
class FaultEvent:
    kind: str                       # "activated" | "deactivated" | "manifested"
    time: float
    fault: str                      # fault name (unique within the campaign)
    fault_type: str                 # class name
    target: str
    parameters: Dict[str, Any] = field(default_factory=dict)   # configured parameters
    sampled: Dict[str, Any] = field(default_factory=dict)      # values drawn at run time
    source: Optional[str] = None    # what caused it: activation model, "trigger:<fault>", "manual", "expired", ...
    seed: Optional[Dict[str, int]] = None                      # campaign seed and the fault's name key

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def __str__(self):
        extra = f" sampled={self.sampled}" if self.sampled else ""
        return f"t={self.time:g} {self.kind:<11} {self.fault} ({self.fault_type} on {self.target}) via {self.source}{extra}"


class EventLog(list):
    """A list of :class:`FaultEvent` with small filtering and export helpers."""

    def filter(self, kind: Optional[str] = None, fault: Optional[str] = None,
               target: Optional[str] = None) -> "EventLog":
        out = EventLog()
        for e in self:
            if kind is not None and e.kind != kind:
                continue
            if fault is not None and e.fault != fault:
                continue
            if target is not None and e.target != target:
                continue
            out.append(e)
        return out

    def counts(self) -> Dict[str, int]:
        c: Dict[str, int] = {}
        for e in self:
            c[e.kind] = c.get(e.kind, 0) + 1
        return c

    def to_dicts(self):
        return [e.to_dict() for e in self]

    def to_json(self, **kw) -> str:
        return json.dumps(self.to_dicts(), **kw)
