"""Serialisable specifications.

Every configurable object in FIBlock (fault, activation model, duration model,
distribution) can describe itself as a plain dictionary via ``spec()`` and be
rebuilt from that dictionary via ``from_spec``. Classes are looked up by name
in a registry; user-defined classes are added with the ``register`` decorator
or passed explicitly to ``from_spec(..., classes={...})``.

Only dataclass fields that are constructor arguments (``init=True``) belong to
a spec; fields with ``init=False`` hold run-time state and are skipped.
"""
from __future__ import annotations

import dataclasses
from typing import Any, Dict, Optional

import numpy as np

_REGISTRY: Dict[str, type] = {}


class _Missing:
    """Singleton marking a value that never arrived (dropped or not yet delivered)."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self):
        return "MISSING"

    def __bool__(self):
        return False

    def __reduce__(self):
        return (_Missing, ())


MISSING = _Missing()


def register(cls):
    """Class decorator: make ``cls`` reconstructible from a spec by its name."""
    _REGISTRY[cls.__name__] = cls
    return cls


def registry() -> Dict[str, type]:
    return dict(_REGISTRY)


def _init_fields(obj):
    return [f for f in dataclasses.fields(obj) if f.init]


def _to_plain(value):
    """Recursively convert a value into JSON-friendly data."""
    if value is MISSING:
        return {"kind": "MISSING"}
    if isinstance(value, Spec):
        return value.spec()
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {"kind": type(value).__name__, **{f.name: _to_plain(getattr(value, f.name)) for f in _init_fields(value)}}
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, (list, tuple)):
        return [_to_plain(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _to_plain(v) for k, v in value.items()}
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if callable(value):
        return {"kind": "Callable", "repr": repr(value)}
    return {"kind": "Opaque", "repr": repr(value)}


def _from_plain(value, classes: Optional[Dict[str, type]] = None):
    """Inverse of ``_to_plain`` for values that carry a ``kind``."""
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
        kwargs = {k: _from_plain(v, classes) for k, v in value.items() if k != "kind"}
        if hasattr(cls, "from_spec_kwargs"):
            return cls.from_spec_kwargs(kwargs, classes)
        return cls(**kwargs)
    if isinstance(value, list):
        return [_from_plain(v, classes) for v in value]
    if isinstance(value, dict):
        return {k: _from_plain(v, classes) for k, v in value.items()}
    return value


class Spec:
    """Mixin: ``spec()`` from dataclass fields, ``from_spec`` via the registry."""

    def spec(self) -> Dict[str, Any]:
        if dataclasses.is_dataclass(self):
            return {"kind": type(self).__name__, **{f.name: _to_plain(getattr(self, f.name)) for f in _init_fields(self)}}
        raise NotImplementedError(f"{type(self).__name__} must override spec()")

    @classmethod
    def from_spec(cls, spec: Dict[str, Any], classes: Optional[Dict[str, type]] = None):
        obj = _from_plain(spec, classes)
        if not isinstance(obj, cls):
            raise TypeError(f"spec described a {type(obj).__name__}, expected {cls.__name__}")
        return obj
