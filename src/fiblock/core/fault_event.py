"""Base class of fault events: *when* a fault activates.

A fault event is polled once per step while its injector is dormant and
eligible. ``poll`` returns ``None`` (stay dormant) or a dict of sampled values
to record (activate now). Events keep their own run-time state, reset by the
injector. They know nothing about the fault type they serve.
"""
from __future__ import annotations

from typing import Optional

from .context import InjectionContext
from .spec import Spec


class FaultEvent(Spec):
    def reset(self, ctx: InjectionContext) -> None:
        return None

    def poll(self, ctx: InjectionContext) -> Optional[dict]:
        return None

    def on_deactivated(self, ctx: InjectionContext) -> None:
        return None
