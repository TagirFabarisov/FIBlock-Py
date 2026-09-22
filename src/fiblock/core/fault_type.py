"""Base class of fault types: *what* the error looks like.

A fault type transforms the value passing through an injection point. It knows
nothing about when it is active or for how long; that is the fault event's and
the fault effect's business, coordinated by the injector.

Constructor arguments are the fault's *parameters*, kept as plain attributes so
that an external program can read, edit, sample or sweep them. By FIBlock
convention the main parameter is called ``value`` (the "fault value").
"""
from __future__ import annotations

import inspect
from typing import Any, Dict, Optional, Tuple

from .context import InjectionContext
from .spec import Spec, to_plain


class FaultType(Spec):
    """Subclass this and implement ``apply``.

    Hooks a subclass may override:

    * ``apply(value, ctx)``        the error: return the corrupted value or ``MISSING``;
    * ``observe(value, ctx)``      sees every pre-fault value at the point, active or not;
    * ``on_activate(ctx)``         may return a dict of sampled values to record;
    * ``on_deactivate(ctx)``       clean-up when the effect ends;
    * ``reset()``                  clear internal state at reset.
    """

    def apply(self, value, ctx: InjectionContext):  # pragma: no cover - abstract
        raise NotImplementedError(f"{type(self).__name__}.apply is not implemented")

    def observe(self, value, ctx: InjectionContext) -> None:
        return None

    def on_activate(self, ctx: InjectionContext) -> Optional[Dict[str, Any]]:
        return None

    def on_deactivate(self, ctx: InjectionContext) -> None:
        return None

    def reset(self) -> None:
        return None

    # ------------------------------------------------------------- parameters
    @classmethod
    def parameter_names(cls) -> Tuple[str, ...]:
        names = []
        for p in inspect.signature(cls.__init__).parameters.values():
            if p.name == "self" or p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
                continue
            names.append(p.name)
        return tuple(names)

    def parameters(self) -> Dict[str, Any]:
        """The configured parameters as a plain dict (live values)."""
        return {n: getattr(self, n) for n in self.parameter_names() if hasattr(self, n)}

    def spec(self) -> Dict[str, Any]:
        return {"kind": type(self).__name__, **to_plain(self.parameters())}

    def __repr__(self):
        params = ", ".join(f"{k}={v!r}" for k, v in self.parameters().items())
        return f"{type(self).__name__}({params})"
