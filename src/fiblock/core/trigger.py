"""The trigger input of an injector: the original block's ``Iflag``.

The trigger input overrules the injector's own fault event: when it fires, the
fault activates regardless of the event's parameters. Wiring one injector's
activation (its ``Fflag`` output in the original block) to another injector's
trigger input is how chained fault injection is built: "in the case of the
fault activation in the first block, the emitted trigger signal would force
the fault activation in the second block". The campaign delivers the
activation records; the trigger decides whether they concern it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional

from .records import ACTIVATION, InjectionRecord
from .spec import Spec, register


@register
@dataclass
class Trigger(Spec):
    """``by`` names the source injector(s): a name, an injector object, or a list
    of them; the trigger fires when one of them activates. ``delay`` (a number
    or a distribution sampled per trigger) is added to the source's activation
    time. ``probability`` lets the trigger fire only sometimes; ``repeat=False``
    lets it fire once per run."""
    by: Any
    delay: Any = 0.0
    probability: float = 1.0
    repeat: bool = True
    _pending: List[dict] = field(default_factory=list, init=False, repr=False, compare=False)
    _fired: bool = field(default=False, init=False, repr=False, compare=False)

    def __post_init__(self):
        from ..distributions import as_distribution
        self.delay = as_distribution(self.delay)

    def sources(self) -> List[str]:
        items = self.by if isinstance(self.by, (list, tuple)) else [self.by]
        return [getattr(b, "name", b) for b in items]

    def reset(self, ctx) -> None:
        self._pending = []
        self._fired = False

    def notify(self, record: InjectionRecord, ctx) -> None:
        """A record from the campaign: schedule an activation if a source injector activated."""
        if record.kind != ACTIVATION or record.injector not in self.sources():
            return
        if record.injector == ctx.injector.name:
            return
        if self._fired and not self.repeat:
            return
        if self.probability < 1.0 and ctx.rng.random() >= self.probability:
            return
        d = self.delay.sample(ctx.rng)
        self._pending.append({"scheduled_time": record.time + d, "trigger_source": record.injector,
                              "trigger_delay": d})

    def poll(self, ctx) -> Optional[dict]:
        """The earliest scheduled activation that is due now, if any."""
        due = [p for p in self._pending if p["scheduled_time"] <= ctx.t]
        if not due:
            return None
        first = min(due, key=lambda p: p["scheduled_time"])
        self._pending = [p for p in self._pending if p is not first]
        self._fired = True
        return dict(first)

    def spec(self):
        return {"kind": "Trigger", "by": self.sources(), "delay": self.delay.spec(),
                "probability": self.probability, "repeat": self.repeat}
