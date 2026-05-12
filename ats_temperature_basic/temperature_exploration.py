from typing import Dict, Optional, Sequence, Tuple

import numpy as np


PresetGapBounds = Tuple[float, float, int, int, float, float]


def preset_ranges_overlap(preset_value_ranges: Dict[int, Tuple[float, float]]) -> bool:
    sorted_ranges = sorted(preset_value_ranges.items(), key=lambda item: item[1][0])
    for index in range(len(sorted_ranges) - 1):
        _, (current_min, current_max) = sorted_ranges[index]
        _, (next_min, _) = sorted_ranges[index + 1]
        if next_min <= current_max:
            return True
    return False


def get_preset_gap_bounds(
    preset_value_ranges: Dict[int, Tuple[float, float]],
) -> Tuple[PresetGapBounds, ...]:
    normalized_ranges = {
        int(key): (float(value[0]), float(value[1]))
        for key, value in preset_value_ranges.items()
    }
    sorted_ranges = sorted(normalized_ranges.items(), key=lambda item: item[1][0])
    preset_gap_bounds = []

    for (left_preset, (_, left_max)), (right_preset, (right_min, _)) in zip(
        sorted_ranges,
        sorted_ranges[1:],
    ):
        if right_min <= left_max:
            continue

        preset_gap_bounds.append(
            (left_max, right_min, left_preset, right_preset, left_max, right_min)
        )

    return tuple(preset_gap_bounds)


def mask_temperatures_between_presets(
    temperatures: np.ndarray,
    preset_gap_bounds: Optional[Sequence[PresetGapBounds]],
) -> np.ndarray:
    if preset_gap_bounds is None:
        return temperatures

    masked_temperatures = np.asarray(temperatures, dtype=float).copy()
    for lower_bound, upper_bound, *_ in preset_gap_bounds:
        gap_mask = (masked_temperatures >= lower_bound) & (masked_temperatures <= upper_bound)
        masked_temperatures[gap_mask] = np.nan
    return masked_temperatures


def extract_temperature_histories(
    frames: np.ndarray,
    coords: np.ndarray,
    averaging_window: int = 1,
) -> np.ndarray:
    temperatures = np.zeros((coords.shape[0], frames.shape[0]))

    for index, (x_coord, y_coord) in enumerate(coords):
        y_min = max(y_coord - averaging_window, 0)
        y_max = min(y_coord + averaging_window + 1, frames.shape[1])
        x_min = max(x_coord - averaging_window, 0)
        x_max = min(x_coord + averaging_window + 1, frames.shape[2])
        window_values = frames[:, y_min:y_max, x_min:x_max]
        temperatures[index] = np.nanmean(window_values, axis=(1, 2))

    return temperatures
