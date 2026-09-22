"""The MISSING sentinel: a value that never arrived (dropped, or not yet delivered)."""
from __future__ import annotations


class _Missing:
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
