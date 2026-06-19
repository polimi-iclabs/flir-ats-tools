"""Reader and SDK utility functions for FLIR ATS files."""

from pathlib import Path
from typing import Any


DEFAULT_OBJECT_PARAMETERS_PATH = Path(__file__).resolve().parent / "object_parameters.json"

_ATS_READER_EXPORTS = {
    "ATSData",
    "ATSInspection",
    "ATSObjectParameters",
    "OBJECT_PARAMETER_DEFINITIONS",
    "ObjectParameterDefinition",
    "apply_object_parameters",
    "build_object_parameter_updates",
    "build_object_parameter_updates_from_mapping",
    "configure_imager",
    "get_available_object_parameters",
    "get_timestamp",
    "inspect_ats_file",
    "list_ats_files",
    "load_object_parameter_updates",
    "normalize_object_parameter_updates",
    "read_ats_file",
}

__all__ = ["DEFAULT_OBJECT_PARAMETERS_PATH"] + sorted(_ATS_READER_EXPORTS)


def __getattr__(name: str) -> Any:
    if name not in _ATS_READER_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    from . import ats_reader

    value = getattr(ats_reader, name)
    globals()[name] = value
    return value
