"""Base class of fault effects: *how long* the fault stays active (its exposure).

``start(ctx)`` is called at activation and may return sampled values to record.
``expired(ctx)`` is polled at every step while the fault is active; the
injector deactivates at the step where it first returns True. Effects know
nothing about the fault type they serve.
"""
from __future__ import annotations

from typing import Optional

from .context import InjectionContext
from .spec import Spec


class FaultEffect(Spec):
    def start(self, ctx: InjectionContext) -> Optional[dict]:
        return None

    def expired(self, ctx: InjectionContext) -> bool:
        return False
