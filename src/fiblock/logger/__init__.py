"""Logger: evidence recording, separate from the injection mechanism.

Two kinds of record: fault-injection records (activation and deactivation of a
fault, produced by the mechanism) and data-error records (an observation made
by the campaign at the injection point, never by the mechanism).
"""
from .data_error import DATA_ERROR, DataErrorRecord, is_data_error
from .injection_log import InjectionLog

__all__ = ["InjectionLog", "DataErrorRecord", "DATA_ERROR", "is_data_error"]
