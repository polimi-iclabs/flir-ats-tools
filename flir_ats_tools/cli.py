"""Basic ATS reading example.

Run from this folder and answer the prompts:

    python example_read_ats.py

or pass the decision explicitly after checking the file once:

    python example_read_ats.py ../In718_ghosttracks_layer_20.ats --export 0 --preset-gap nan

Object parameters are loaded from object_parameters.json by default. Use
--object-parameters-config to point at another JSON file, and use individual
object-parameter flags to override that config for a single run.

Exported frames are saved by default in:

    ats_temperature_basic/exported_frames/
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

import numpy as np


DEFAULT_ATS_PATH = Path(__file__).resolve().parent.parent / "In718_ghosttracks_layer_20.ats"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "exported_frames"
DEFAULT_OBJECT_PARAMETERS_PATH = Path(__file__).resolve().parent / "object_parameters.json"
EXPORT_ALL_PRESETS = "all-presets"
EXPORT_SUPERFRAME = "superframe"
PRESET_GAP_CHOICES = ("ask", "keep", "nan")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect an ATS file, then read selected temperature frames.")
    parser.add_argument(
        "ats_path",
        nargs="?",
        type=Path,
        default=DEFAULT_ATS_PATH,
        help="ATS file to read. Defaults to the sample ATS file in the parent folder.",
    )
    parser.add_argument(
        "--export",
        default="ask",
        help=(
            "What to export after inspection: a preset number found in the file, "
            "all-presets, or superframe when the file supports superframing."
        ),
    )
    parser.add_argument(
        "--preset-gap",
        choices=PRESET_GAP_CHOICES,
        default="ask",
        help="For superframes, keep or replace values between preset temperature ranges with NaN.",
    )
    parser.add_argument(
        "--emissivity",
        type=float,
        default=None,
        help="Override config emissivity with a 0..1 fraction.",
    )
    parser.add_argument(
        "--reflected-temp-k",
        dest="reflected_temp_k",
        type=float,
        default=None,
        help="Override config reflected_temp in Kelvin.",
    )
    parser.add_argument(
        "--distance-m",
        dest="distance_m",
        type=float,
        default=None,
        help="Override config distance in meters.",
    )
    parser.add_argument(
        "--atmosphere-temp-k",
        dest="atmosphere_temp_k",
        type=float,
        default=None,
        help="Override config atmosphere_temp in Kelvin.",
    )
    parser.add_argument(
        "--relative-humidity",
        type=float,
        default=None,
        help="Override config relative humidity as a 0..1 fraction. Use 0.50 for 50%%.",
    )
    parser.add_argument(
        "--atmospheric-transmission",
        type=float,
        default=None,
        help="Override config atmospheric transmission as a 0..1 fraction.",
    )
    parser.add_argument(
        "--est-atmospheric-transmission",
        choices=("true", "false"),
        default=None,
        help="Override config est_atmospheric_transmission.",
    )
    parser.add_argument(
        "--ext-optics-temp-k",
        dest="ext_optics_temp_k",
        type=float,
        default=None,
        help="Override config ext_optics_temp in Kelvin.",
    )
    parser.add_argument(
        "--ext-optics-transmission",
        dest="ext_optics_transmission",
        type=float,
        default=None,
        help="Override config ext_optics_transmission as a 0..1 fraction.",
    )
    parser.add_argument(
        "--source",
        default=None,
        help="Override config source with a value accepted by the FLIR SDK.",
    )
    parser.add_argument(
        "--object-parameters-config",
        type=Path,
        default=DEFAULT_OBJECT_PARAMETERS_PATH,
        help="JSON file with object parameters. Defaults to object_parameters.json in this folder.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Folder where the exported .npz frame stack will be saved.",
    )
    return parser.parse_args()


def format_temperature_range(value_range: Optional[tuple[float, float]]) -> str:
    if value_range is None:
        return "temperature range unavailable"

    lower_bound, upper_bound = value_range
    return f"{lower_bound:.3f} K to {upper_bound:.3f} K"


def print_ats_description(inspection, preset_gap_bounds: Sequence[tuple[float, float, int, int, float, float]]) -> None:
    print("\nATS content:")
    print(f"  File: {inspection.path}")
    print(f"  Raw frames in file: {inspection.num_frames}")
    print(f"  Frame size: {inspection.height} rows x {inspection.width} columns")

    if inspection.available_presets:
        print("  Presets found:")
        for preset in inspection.available_presets:
            preset_range = inspection.preset_value_ranges.get(preset)
            print(
                f"    preset {preset}: observed raw temperature range "
                f"{format_temperature_range(preset_range)}"
            )
    else:
        print("  Presets found: none reported by the file")

    if inspection.is_superframe:
        print("  Superframing: available")
    else:
        print("  Superframing: not available for this ATS file")

    if preset_gap_bounds:
        print("  Gaps between adjacent preset ranges:")
        for lower_bound, upper_bound, left_preset, right_preset, left_max, right_min in preset_gap_bounds:
            print(
                f"    preset {left_preset} max {left_max:.3f} K to "
                f"preset {right_preset} min {right_min:.3f} K "
                f"=> {lower_bound:.3f} K to {upper_bound:.3f} K"
            )


def print_object_parameters(object_parameters: Mapping[str, Any]) -> None:
    print("\nObject parameters applied before reading:")
    if not object_parameters:
        print("  none")
        return

    for parameter_name in sorted(object_parameters):
        print(f"  {parameter_name}: {object_parameters[parameter_name]}")


def get_cli_object_parameter_overrides(args: argparse.Namespace) -> dict[str, Any]:
    if args.est_atmospheric_transmission is None:
        est_atmospheric_transmission = None
    else:
        est_atmospheric_transmission = args.est_atmospheric_transmission == "true"

    possible_overrides = {
        "emissivity": args.emissivity,
        "reflected_temp": args.reflected_temp_k,
        "distance": args.distance_m,
        "atmosphere_temp": args.atmosphere_temp_k,
        "relative_humidity": args.relative_humidity,
        "atmospheric_transmission": args.atmospheric_transmission,
        "est_atmospheric_transmission": est_atmospheric_transmission,
        "ext_optics_temp": args.ext_optics_temp_k,
        "ext_optics_transmission": args.ext_optics_transmission,
        "source": args.source,
    }
    return {
        parameter_name: parameter_value
        for parameter_name, parameter_value in possible_overrides.items()
        if parameter_value is not None
    }


def build_export_options(inspection) -> list[tuple[str, str]]:
    options = []
    for preset in inspection.available_presets:
        preset_range = inspection.preset_value_ranges.get(preset)
        options.append(
            (
                f"preset:{preset}",
                f"preset {preset} only ({format_temperature_range(preset_range)})",
            )
        )

    if inspection.available_presets:
        options.append((EXPORT_ALL_PRESETS, "all raw preset frames"))

    if inspection.is_superframe:
        options.append((EXPORT_SUPERFRAME, "superframes only"))

    return options


def print_export_options(options: Sequence[tuple[str, str]]) -> None:
    print("\nExport options for this file:")
    for index, (_, description) in enumerate(options, start=1):
        print(f"  {index}. {description}")


def normalize_export_selection(selection: str, inspection) -> str:
    cleaned_selection = selection.strip().lower().replace("_", "-")

    if cleaned_selection in {"all", EXPORT_ALL_PRESETS}:
        if not inspection.available_presets:
            raise ValueError("Cannot export all presets because this file reports no presets.")
        return EXPORT_ALL_PRESETS

    if cleaned_selection == EXPORT_SUPERFRAME:
        if not inspection.is_superframe:
            raise ValueError("Cannot export superframes because this ATS file does not support superframing.")
        return EXPORT_SUPERFRAME

    for prefix in ("preset:", "preset-", "preset "):
        if cleaned_selection.startswith(prefix):
            cleaned_selection = cleaned_selection[len(prefix):]
            break

    try:
        preset = int(cleaned_selection)
    except ValueError as exc:
        available = ", ".join(str(preset) for preset in inspection.available_presets)
        if inspection.is_superframe:
            available = f"{available}, {EXPORT_SUPERFRAME}" if available else EXPORT_SUPERFRAME
        if inspection.available_presets:
            available = f"{available}, {EXPORT_ALL_PRESETS}"
        raise ValueError(f"Unsupported export selection {selection!r}. Available options: {available}.") from exc

    if preset not in inspection.available_presets:
        available = ", ".join(str(value) for value in inspection.available_presets) or "none"
        raise ValueError(f"Preset {preset} is not available in this file. Available presets: {available}.")

    return f"preset:{preset}"


def prompt_export_selection(options: Sequence[tuple[str, str]]) -> str:
    if not options:
        raise ValueError("No preset or superframe export options were found in this ATS file.")

    print_export_options(options)
    while True:
        answer = input("Select export option by number or name [1]: ").strip().lower()
        if not answer:
            return options[0][0]

        if answer.isdigit():
            option_index = int(answer) - 1
            if 0 <= option_index < len(options):
                return options[option_index][0]

        for key, description in options:
            if answer == key or answer == description.lower():
                return key

        print("Please choose one of the displayed options.")


def resolve_export_selection(value: str, inspection) -> str:
    options = build_export_options(inspection)
    if value != "ask":
        return normalize_export_selection(value, inspection)

    if not sys.stdin.isatty():
        raise ValueError("No interactive terminal found. Pass --export with a preset number, all-presets, or superframe.")

    return prompt_export_selection(options)


def prompt_preset_gap_action(default: str = "keep") -> str:
    while True:
        answer = input(f"Superframe values between preset ranges: keep or nan [{default}]: ").strip().lower()
        if not answer:
            return default
        if answer in PRESET_GAP_CHOICES[1:]:
            return answer

        print("Please choose keep or nan.")


def resolve_preset_gap_action(value: str, should_prompt: bool) -> str:
    if not should_prompt:
        return "keep" if value == "ask" else value

    if value != "ask":
        return value

    if not sys.stdin.isatty():
        raise ValueError("No interactive terminal found. Pass --preset-gap keep or --preset-gap nan.")

    return prompt_preset_gap_action(default="keep")


def selection_to_reader_options(selection: str) -> tuple[str, Optional[int]]:
    if selection.startswith("preset:"):
        return "preset", int(selection.split(":", maxsplit=1)[1])
    if selection == EXPORT_ALL_PRESETS:
        return "all_presets", None
    if selection == EXPORT_SUPERFRAME:
        return "superframe", None

    raise ValueError(f"Unsupported export selection: {selection}")


def export_label(selection: str, preset_gap_action: str) -> str:
    if selection.startswith("preset:"):
        return f"preset_{selection.split(':', maxsplit=1)[1]}"
    if selection == EXPORT_ALL_PRESETS:
        return "all_presets"
    if selection == EXPORT_SUPERFRAME:
        return f"superframe_gap_{preset_gap_action}"

    raise ValueError(f"Unsupported export selection: {selection}")


def save_exported_frames(
    output_dir: Path,
    ats_path: Path,
    frames: np.ndarray,
    ats_data,
    export_selection: str,
    preset_gap_action: str,
    preset_gap_bounds: Sequence[tuple[float, float, int, int, float, float]],
    object_parameters: Mapping[str, Any],
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    label = export_label(export_selection, preset_gap_action)
    output_path = output_dir / f"{ats_path.stem}_{label}.npz"

    preset_keys = np.asarray(sorted(ats_data.preset_value_ranges), dtype=int)
    preset_mins = np.asarray(
        [ats_data.preset_value_ranges[int(key)][0] for key in preset_keys],
        dtype=float,
    )
    preset_maxs = np.asarray(
        [ats_data.preset_value_ranges[int(key)][1] for key in preset_keys],
        dtype=float,
    )
    object_parameter_keys = sorted(object_parameters)
    object_parameter_names = np.asarray(object_parameter_keys, dtype=str)
    object_parameter_values_json = np.asarray(
        [json.dumps(object_parameters[parameter_name]) for parameter_name in object_parameter_keys],
        dtype=str,
    )

    np.savez_compressed(
        output_path,
        frames=frames,
        relative_time=ats_data.relative_time,
        frame_indices=ats_data.frame_indices,
        frame_presets=ats_data.frame_presets,
        timestamps_utc=np.asarray([timestamp.isoformat() for timestamp in ats_data.timestamps]),
        source_path=np.asarray(str(ats_path)),
        export_selection=np.asarray(export_selection),
        read_mode=np.asarray(ats_data.read_mode),
        preset_gap_action=np.asarray(preset_gap_action),
        preset_gap_bounds=np.asarray(preset_gap_bounds, dtype=float),
        available_presets=np.asarray(ats_data.available_presets, dtype=int),
        preset_value_range_presets=preset_keys,
        preset_value_range_min=preset_mins,
        preset_value_range_max=preset_maxs,
        object_parameter_names=object_parameter_names,
        object_parameter_values_json=object_parameter_values_json,
        emissivity=np.asarray(object_parameters.get("emissivity", np.nan), dtype=float),
    )
    return output_path


def print_value_summary(label: str, values: np.ndarray) -> None:
    finite_values = np.asarray(values)[np.isfinite(values)]
    if finite_values.size == 0:
        print(f"{label}: no finite values")
        return

    print(
        f"{label}: min={np.min(finite_values):.3f} K | "
        f"mean={np.mean(finite_values):.3f} K | "
        f"max={np.max(finite_values):.3f} K"
    )


def print_frame_preset_counts(frame_presets: np.ndarray) -> None:
    if frame_presets.size == 0:
        return

    values, counts = np.unique(frame_presets, return_counts=True)
    count_parts = []
    for value, count in zip(values, counts):
        label = "unknown" if int(value) < 0 else f"preset {int(value)}"
        count_parts.append(f"{label}: {int(count)}")

    print(f"Frame preset counts: {', '.join(count_parts)}")


def find_peak_index(history: np.ndarray) -> Optional[int]:
    finite_mask = np.isfinite(history)
    if not np.any(finite_mask):
        return None

    finite_indices = np.flatnonzero(finite_mask)
    local_peak_index = int(np.argmax(history[finite_mask]))
    return int(finite_indices[local_peak_index])


def main() -> None:
    args = parse_args()
    ats_path = args.ats_path.expanduser()
    output_dir = args.output_dir.expanduser()
    if not ats_path.exists():
        raise FileNotFoundError(f"ATS file not found: {ats_path}")

    # Import ATS-specific modules after argument parsing so `--help` works
    # even on machines where the FLIR/Teledyne fnv package is not installed yet.
    from ats_reader import (
        build_object_parameter_updates_from_mapping,
        inspect_ats_file,
        load_object_parameter_updates,
        read_ats_file,
    )
    from temperature_exploration import (
        extract_temperature_histories,
        get_preset_gap_bounds,
        mask_temperatures_between_presets,
    )

    object_parameters_config_path = args.object_parameters_config.expanduser()
    object_parameters = load_object_parameter_updates(object_parameters_config_path)
    object_parameter_overrides = build_object_parameter_updates_from_mapping(
        get_cli_object_parameter_overrides(args)
    )
    object_parameters = {**object_parameters, **object_parameter_overrides}
    print(f"\nObject parameter config: {object_parameters_config_path}")
    print_object_parameters(object_parameters)
    inspection = inspect_ats_file(str(ats_path), object_parameter_updates=object_parameters)
    preset_gap_bounds = get_preset_gap_bounds(inspection.preset_value_ranges)
    print_ats_description(inspection, preset_gap_bounds)

    export_selection = resolve_export_selection(args.export, inspection)
    read_mode, preset = selection_to_reader_options(export_selection)
    should_handle_preset_gap = export_selection == EXPORT_SUPERFRAME and bool(preset_gap_bounds)
    preset_gap_action = resolve_preset_gap_action(args.preset_gap, should_prompt=should_handle_preset_gap)

    # read_ats_file returns an ATSData dataclass with:
    # frames: temperature stack shaped as (n_frames, height, width)
    # timestamps: absolute UTC timestamps for each frame
    # relative_time: seconds from the first valid frame
    ats_data = read_ats_file(
        str(ats_path),
        preset=preset,
        read_mode=read_mode,
        object_parameter_updates=object_parameters,
        inspection=inspection,
    )

    frames = ats_data.frames
    print(f"\nLoaded: {ats_data.path}")
    print(f"Export selected: {export_selection}  # reader mode: {ats_data.read_mode}")
    print(f"Frames shape: {frames.shape}  # (frames, rows, columns)")
    print(
        f"Relative time span: {ats_data.relative_time[0]:.6f} s "
        f"to {ats_data.relative_time[-1]:.6f} s"
    )
    print(f"Available presets: {ats_data.available_presets}")
    print(f"Superframing detected: {ats_data.is_superframe}")
    print_frame_preset_counts(ats_data.frame_presets)

    if export_selection == EXPORT_SUPERFRAME and preset_gap_action == "nan":
        frames = mask_temperatures_between_presets(frames, preset_gap_bounds)
        print("Preset-gap handling: replaced in-between superframe values with NaN.")
    elif export_selection == EXPORT_SUPERFRAME:
        print("Preset-gap handling: kept in-between superframe values.")
    else:
        print("Preset-gap handling: not applicable because raw preset frames were selected.")

    output_path = save_exported_frames(
        output_dir=output_dir,
        ats_path=ats_path,
        frames=frames,
        ats_data=ats_data,
        export_selection=export_selection,
        preset_gap_action=preset_gap_action,
        preset_gap_bounds=preset_gap_bounds,
        object_parameters=object_parameters,
    )
    print(f"Exported frames saved to: {output_path}")

    # Basic whole-stack summaries.
    print_value_summary("All frame values", frames)
    print_value_summary("Average temperature map", np.nanmean(frames, axis=0))
    print_value_summary("Maximum temperature map", np.nanmax(frames, axis=0))

    # Extract the temperature history at the center pixel.
    # Coordinates are passed as (x, y), while frames are indexed as [frame, y, x].
    center_coord = np.array([[frames.shape[2] // 2, frames.shape[1] // 2]], dtype=int)
    center_history = extract_temperature_histories(frames, center_coord, averaging_window=1)[0]
    peak_index = find_peak_index(center_history)

    print(f"Center coordinate (x, y): {tuple(center_coord[0])}")
    print_value_summary("Center 3x3 temperature history", center_history)
    if peak_index is not None:
        print(
            f"Center history peak: {center_history[peak_index]:.3f} K "
            f"at t={ats_data.relative_time[peak_index]:.6f} s"
        )


if __name__ == "__main__":
    main()
