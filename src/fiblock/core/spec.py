"""Specifications: every configurable object describes itself as plain data.

``spec()`` turns a fault type, fault event, fault effect, distribution or
injector into a dictionary of built-in Python values; ``from_spec`` rebuilds
it. Classes are found by name in a registry filled by the ``register``
decorator (all built-ins are registered; user classes may be). Only dataclass
fields that are constructor arguments belong to a spec; run-time state
(``init=False`` fields) is skipped.
"""
from __future__ import annotations

import dataclasses
from typing import Any, Dict, Optional

import numpy as np

from .missing import MISSING

_REGISTRY: Dict[str, type] = {}


def register(cls):
    """Class decorator: make ``cls`` reconstructible from a spec by its name."""
    _REGISTRY[cls.__name__] = cls
    return cls


def registry() -> Dict[str, type]:
    return dict(_REGISTRY)


def _init_fields(obj):
    return [f for f in dataclasses.fields(obj) if f.init]


def to_plain(value):
    """Recursively convert a value into JSON-friendly data."""
    if value is MISSING:
        return {"kind": "MISSING"}
    if isinstance(value, Spec):
        return value.spec()
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {"kind": type(value).__name__, **{f.name: to_plain(getattr(value, f.name)) for f in _init_fields(value)}}
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, (list, tuple)):
        return [to_plain(v) for v in value]
    if isinstance(value, dict):
        return {str(k): to_plain(v) for k, v in value.items()}
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if callable(value):
        return {"kind": "Callable", "repr": repr(value)}
    return {"kind": "Opaque", "repr": repr(value)}


def from_plain(value, classes: Optional[Dict[str, type]] = None):
    """Inverse of :func:`to_plain` for values that carry a ``kind``."""
    if isinstance(value, dict) and "kind" in value:
        kind = value["kind"]
        if kind == "MISSING":
            return MISSING
        if kind in ("Callable", "Opaque", "FromCallable", "Scipy"):
            raise ValueError(
                f"cannot rebuild a {kind} from a spec ({value.get('repr')}); "
                "supply the object again in code instead of replaying it from a spec"
            )
        cls = (classes or {}).get(kind) or _REGISTRY.get(kind)
        if cls is None:
            raise KeyError(f"unknown kind {kind!r}; register the class or pass classes={{...}}")
        kwargs = {k: from_plain(v, classes) for k, v in value.items() if k != "kind"}
        if hasattr(cls, "from_spec_kwargs"):
            return cls.from_spec_kwargs(kwargs, classes)
        return cls(**kwargs)
    if isinstance(value, list):
        return [from_plain(v, classes) for v in value]
    if isinstance(value, dict):
        return {k: from_plain(v, classes) for k, v in value.items()}
    return value


class Spec:
    """Mixin: ``spec()`` from dataclass fields, ``from_spec`` via the registry."""

    def spec(self) -> Dict[str, Any]:
        if dataclasses.is_dataclass(self):
            return {"kind": type(self).__name__, **{f.name: to_plain(getattr(self, f.name)) for f in _init_fields(self)}}
        raise NotImplementedError(f"{type(self).__name__} must override spec()")

    @classmethod
    def from_spec(cls, spec: Dict[str, Any], classes: Optional[Dict[str, type]] = None):
        obj = from_plain(spec, classes)
        if not isinstance(obj, cls):
            raise TypeError(f"spec described a {type(obj).__name__}, expected {cls.__name__}")
        return obj
