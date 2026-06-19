"""Analysis helpers for FLIR ATS temperature data."""

from .temperature import (
    PresetGapBounds,
    extract_temperature_histories,
    get_preset_gap_bounds,
    mask_temperatures_between_presets,
    preset_ranges_overlap,
)

__all__ = [
    "PresetGapBounds",
    "extract_temperature_histories",
    "get_preset_gap_bounds",
    "mask_temperatures_between_presets",
    "preset_ranges_overlap",
]
