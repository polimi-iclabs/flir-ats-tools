import datetime
import json
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple, Union

import fnv
import fnv.file
import fnv.reduce
import numpy as np


@dataclass(frozen=True)
class ObjectParameterDefinition:
    name: str
    expected_value: str
    when_to_set: str


@dataclass(frozen=True)
class ATSObjectParameters:
    """Radiometric object parameters applied before frames are loaded.

    Emissivity defaults to 1.0. Leave the other optional values as None to keep
    the values stored in the ATS file. Temperatures are expected in Kelvin
    because this reader requests Kelvin output from the FLIR Science File SDK.
    """

    emissivity: Optional[float] = 1.0
    reflected_temp: Optional[float] = None
    distance: Optional[float] = None
    atmosphere_temp: Optional[float] = None
    relative_humidity: Optional[float] = None
    atmospheric_transmission: Optional[float] = None
    est_atmospheric_transmission: Optional[bool] = None
    ext_optics_temp: Optional[float] = None
    ext_optics_transmission: Optional[float] = None
    source: Optional[Any] = None

    def to_updates(self) -> Dict[str, Any]:
        return {
            field.name: getattr(self, field.name)
            for field in fields(self)
            if getattr(self, field.name) is not None
        }


ObjectParameterUpdates = Union[Mapping[str, Any], ATSObjectParameters]
PathLike = Union[str, Path]
DEFAULT_OBJECT_PARAMETERS_PATH = Path(__file__).resolve().parent / "object_parameters.json"


OBJECT_PARAMETER_DEFINITIONS: Tuple[ObjectParameterDefinition, ...] = (
    ObjectParameterDefinition(
        name="emissivity",
        expected_value="unitless fraction from 0 to 1",
        when_to_set="Set for every temperature read. Use 1.0 for blackbody-like calibrated data.",
    ),
    ObjectParameterDefinition(
        name="reflected_temp",
        expected_value="Kelvin",
        when_to_set="Set when emissivity is below 1.0 or the surroundings differ from the target.",
    ),
    ObjectParameterDefinition(
        name="distance",
        expected_value="meters",
        when_to_set="Set when the object-camera distance is known, especially for longer paths.",
    ),
    ObjectParameterDefinition(
        name="atmosphere_temp",
        expected_value="Kelvin",
        when_to_set="Set when atmospheric compensation matters for the measurement setup.",
    ),
    ObjectParameterDefinition(
        name="relative_humidity",
        expected_value="unitless fraction from 0 to 1",
        when_to_set="Set when atmospheric compensation matters. Use 0.50 for 50%.",
    ),
    ObjectParameterDefinition(
        name="atmospheric_transmission",
        expected_value="unitless fraction from 0 to 1",
        when_to_set="Set only when you want to override the SDK/camera transmission estimate.",
    ),
    ObjectParameterDefinition(
        name="est_atmospheric_transmission",
        expected_value="boolean",
        when_to_set="Set when you want the SDK to estimate atmospheric transmission.",
    ),
    ObjectParameterDefinition(
        name="ext_optics_temp",
        expected_value="Kelvin",
        when_to_set="Set when an external lens, IR window, or heat shield is in the optical path.",
    ),
    ObjectParameterDefinition(
        name="ext_optics_transmission",
        expected_value="unitless fraction from 0 to 1",
        when_to_set="Set when external optics are in the optical path. Use 1.0 when absent.",
    ),
    ObjectParameterDefinition(
        name="source",
        expected_value="value accepted by the FLIR SDK",
        when_to_set="Leave unset unless your camera setup requires an explicit source parameter.",
    ),
)


@dataclass
class ATSInspection:
    path: str
    num_frames: int
    height: int
    width: int
    available_presets: Tuple[int, ...]
    preset_value_ranges: Dict[int, Tuple[float, float]]
    is_superframing: bool
    is_superframe: bool


@dataclass
class ATSData:
    path: str
    frames: np.ndarray
    timestamps: List[datetime.datetime]
    relative_time: np.ndarray
    frame_indices: np.ndarray
    frame_presets: np.ndarray
    preset: Optional[int]
    available_presets: Tuple[int, ...]
    preset_value_ranges: Dict[int, Tuple[float, float]]
    is_superframing: bool
    is_superframe: bool
    read_mode: str
    height: int
    width: int


def _validate_fraction(parameter_name: str, value: Optional[float]) -> None:
    if value is None:
        return
    if not 0.0 <= value <= 1.0:
        raise ValueError(
            f"{parameter_name} must be a fraction between 0 and 1. "
            "Use 0.50 for 50%."
        )


def _validate_positive(parameter_name: str, value: Optional[float], unit: str) -> None:
    if value is None:
        return
    if value <= 0:
        raise ValueError(f"{parameter_name} must be greater than zero ({unit}).")


def build_object_parameter_updates(
    *,
    emissivity: Optional[float] = 1.0,
    reflected_temp: Optional[float] = None,
    distance: Optional[float] = None,
    atmosphere_temp: Optional[float] = None,
    relative_humidity: Optional[float] = None,
    atmospheric_transmission: Optional[float] = None,
    est_atmospheric_transmission: Optional[bool] = None,
    ext_optics_temp: Optional[float] = None,
    ext_optics_transmission: Optional[float] = None,
    source: Optional[Any] = None,
) -> Dict[str, Any]:
    """Build the object-parameter mapping accepted by inspect_ats_file/read_ats_file.

    Emissivity is included by default. Pass None for the other parameters when
    they should be left at the value stored in the ATS metadata. Fractions use
    0..1 notation, not percentages.
    """

    _validate_fraction("emissivity", emissivity)
    _validate_fraction("relative_humidity", relative_humidity)
    _validate_fraction("atmospheric_transmission", atmospheric_transmission)
    _validate_fraction("ext_optics_transmission", ext_optics_transmission)
    _validate_positive("reflected_temp", reflected_temp, "Kelvin")
    _validate_positive("distance", distance, "meters")
    _validate_positive("atmosphere_temp", atmosphere_temp, "Kelvin")
    _validate_positive("ext_optics_temp", ext_optics_temp, "Kelvin")

    return ATSObjectParameters(
        emissivity=emissivity,
        reflected_temp=reflected_temp,
        distance=distance,
        atmosphere_temp=atmosphere_temp,
        relative_humidity=relative_humidity,
        atmospheric_transmission=atmospheric_transmission,
        est_atmospheric_transmission=est_atmospheric_transmission,
        ext_optics_temp=ext_optics_temp,
        ext_optics_transmission=ext_optics_transmission,
        source=source,
    ).to_updates()


def build_object_parameter_updates_from_mapping(
    object_parameter_values: Mapping[str, Any],
) -> Dict[str, Any]:
    """Validate a mapping of object-parameter names and return SDK updates."""

    parameter_names = {field.name for field in fields(ATSObjectParameters)}
    unsupported_names = sorted(set(object_parameter_values) - parameter_names)
    if unsupported_names:
        allowed_names = ", ".join(sorted(parameter_names))
        raise ValueError(
            "Unsupported object parameter config key(s): "
            f"{', '.join(unsupported_names)}. Allowed keys: {allowed_names}."
        )

    object_parameter_kwargs = {
        parameter_name: object_parameter_values[parameter_name]
        for parameter_name in parameter_names
        if parameter_name in object_parameter_values
    }
    if "emissivity" not in object_parameter_kwargs:
        object_parameter_kwargs["emissivity"] = None

    return build_object_parameter_updates(**object_parameter_kwargs)


def load_object_parameter_updates(config_path: PathLike = DEFAULT_OBJECT_PARAMETERS_PATH) -> Dict[str, Any]:
    """Load object parameters from a JSON config file."""

    resolved_config_path = Path(config_path).expanduser()
    if not resolved_config_path.exists():
        raise FileNotFoundError(f"Object-parameter config not found: {resolved_config_path}")

    with resolved_config_path.open("r", encoding="utf-8") as config_file:
        config_data = json.load(config_file)

    if not isinstance(config_data, dict):
        raise ValueError(
            f"Object-parameter config must contain a JSON object: {resolved_config_path}"
        )

    return build_object_parameter_updates_from_mapping(config_data)


def normalize_object_parameter_updates(
    object_parameter_updates: Optional[ObjectParameterUpdates],
) -> Dict[str, Any]:
    if object_parameter_updates is None:
        return {}
    if isinstance(object_parameter_updates, ATSObjectParameters):
        return object_parameter_updates.to_updates()
    return {
        parameter_name: parameter_value
        for parameter_name, parameter_value in object_parameter_updates.items()
        if parameter_value is not None
    }


def get_available_object_parameters(imager: fnv.file.ImagerFile) -> Dict[str, Any]:
    """Return public object-parameter names exposed by the installed SDK."""

    object_parameters = imager.object_parameters
    available_parameters: Dict[str, Any] = {}
    for parameter_name in dir(object_parameters):
        if parameter_name.startswith("_"):
            continue

        try:
            parameter_value = getattr(object_parameters, parameter_name)
        except Exception:
            continue

        if callable(parameter_value):
            continue

        available_parameters[parameter_name] = parameter_value

    return available_parameters


def list_ats_files(
    folder: PathLike,
    max_files: Optional[int] = None,
) -> List[Path]:
    """Return ATS files in a folder, skipping macOS resource-fork files."""

    folder_path = Path(folder).expanduser().resolve()
    if not folder_path.exists():
        raise FileNotFoundError(f"ATS folder not found: {folder_path}")
    if not folder_path.is_dir():
        raise NotADirectoryError(f"ATS path is not a folder: {folder_path}")
    if max_files is not None and max_files <= 0:
        raise ValueError("max_files must be greater than zero, or None.")

    ats_files = [
        path
        for path in folder_path.glob("*.ats")
        if not path.name.startswith("._")
    ]

    ats_files = sorted(ats_files)

    if max_files is not None:
        ats_files = ats_files[:max_files]

    return ats_files


def get_timestamp(frame_info: Iterable[Dict]) -> Optional[datetime.datetime]:
    for field in frame_info:
        if field["name"] != "Time":
            continue

        date_str = field["value"]
        microsecond = int(date_str[-6:])
        second = int(date_str[-9:-7])
        minute = int(date_str[7:9])
        hour = int(date_str[4:6])
        day_of_year = int(date_str[0:3])
        year = datetime.datetime.now().year

        month = datetime.datetime.strptime(str(day_of_year), "%j").month
        day = datetime.datetime.strptime(str(day_of_year), "%j").day

        return datetime.datetime(
            tzinfo=datetime.timezone.utc,
            year=year,
            month=month,
            day=day,
            hour=hour,
            minute=minute,
            second=second,
            microsecond=microsecond,
        )

    return None


def apply_object_parameters(
    imager: fnv.file.ImagerFile,
    object_parameter_updates: Optional[ObjectParameterUpdates] = None,
) -> None:
    normalized_updates = normalize_object_parameter_updates(object_parameter_updates)
    if not normalized_updates:
        return

    object_parameters = imager.object_parameters
    for parameter_name, parameter_value in normalized_updates.items():
        if not hasattr(object_parameters, parameter_name):
            available = ", ".join(sorted(get_available_object_parameters(imager))) or "none"
            raise ValueError(
                f"Unsupported object parameter: {parameter_name}. "
                f"Available object parameters exposed by this SDK/file: {available}."
            )
        setattr(object_parameters, parameter_name, parameter_value)
    imager.object_parameters = object_parameters


def configure_imager(imager: fnv.file.ImagerFile) -> None:
    if imager.has_unit(fnv.Unit.TEMPERATURE_FACTORY):
        imager.unit = fnv.Unit.TEMPERATURE_FACTORY
        imager.temp_type = fnv.TempType.KELVIN
    else:
        imager.unit = fnv.Unit.COUNTS

    apply_object_parameters(imager, ATSObjectParameters(emissivity=1.0))


def _load_frame(imager: fnv.file.ImagerFile, frame_index: int, use_superframe: bool) -> None:
    if use_superframe and hasattr(imager, "get_superframe"):
        imager.get_superframe(frame_index)
        return

    if hasattr(imager, "get_frame"):
        imager.get_frame(frame_index)
        return

    imager.get_superframe(frame_index)


def _is_superframing_file(imager: fnv.file.ImagerFile) -> bool:
    return bool(
        getattr(imager, "is_superframing", False)
        or getattr(imager, "is_superframe", False)
    )


def _inspect_presets(imager: fnv.file.ImagerFile) -> Tuple[Tuple[int, ...], bool]:
    observed_presets = []
    frames_to_probe = min(imager.num_frames, 12)
    is_superframing = _is_superframing_file(imager)

    for frame_index in range(frames_to_probe):
        _load_frame(imager, frame_index, use_superframe=is_superframing)
        current_preset = getattr(imager, "preset", None)
        if current_preset is None:
            continue
        observed_presets.append(int(current_preset))

    available_presets = tuple(sorted(set(observed_presets)))

    return available_presets, is_superframing


def _collect_preset_value_ranges(imager: fnv.file.ImagerFile) -> Dict[int, Tuple[float, float]]:
    preset_value_ranges: Dict[int, Tuple[float, float]] = {}
    for frame_index in range(imager.num_frames):
        _load_frame(imager, frame_index, use_superframe=False)
        frame_preset = getattr(imager, "preset", None)
        if frame_preset is None:
            continue

        frame_preset = int(frame_preset)
        frame = np.array(imager.final, copy=False).reshape((imager.height, imager.width))
        frame_min = float(np.min(frame))
        frame_max = float(np.max(frame))

        if frame_preset not in preset_value_ranges:
            preset_value_ranges[frame_preset] = (frame_min, frame_max)
            continue

        current_min, current_max = preset_value_ranges[frame_preset]
        preset_value_ranges[frame_preset] = (
            min(current_min, frame_min),
            max(current_max, frame_max),
        )

    return preset_value_ranges


def inspect_ats_file(
    path: str,
    object_parameter_updates: Optional[ObjectParameterUpdates] = None,
    collect_preset_value_ranges: bool = True,
) -> ATSInspection:
    imager = fnv.file.ImagerFile(path)
    configure_imager(imager)
    apply_object_parameters(imager, object_parameter_updates)

    observed_presets, is_superframing = _inspect_presets(imager)
    if collect_preset_value_ranges:
        preset_value_ranges = _collect_preset_value_ranges(imager)
    else:
        preset_value_ranges = {}
    available_presets = tuple(sorted(set(observed_presets).union(preset_value_ranges)))

    return ATSInspection(
        path=path,
        num_frames=imager.num_frames,
        height=imager.height,
        width=imager.width,
        available_presets=available_presets,
        preset_value_ranges=preset_value_ranges,
        is_superframing=is_superframing,
        is_superframe=is_superframing,
    )


def _resolve_read_mode(read_mode: Optional[str], preset: Optional[int], is_superframing: bool) -> str:
    valid_read_modes = {"preset", "all_presets", "superframe"}
    if read_mode is None:
        if preset is not None:
            return "preset"
        return "all_presets"

    if read_mode not in valid_read_modes:
        raise ValueError(
            f"Unsupported read_mode={read_mode!r}. "
            f"Use one of: {', '.join(sorted(valid_read_modes))}."
        )

    if read_mode == "preset" and preset is None:
        raise ValueError("read_mode='preset' requires a preset number.")

    if read_mode in {"all_presets", "superframe"} and preset is not None:
        raise ValueError(f"preset cannot be combined with read_mode={read_mode!r}.")

    return read_mode


def _resolve_frame_limit(max_frames: Optional[int]) -> Optional[int]:
    if max_frames is None:
        return None

    frame_limit = int(max_frames)
    if frame_limit <= 0:
        raise ValueError("max_frames must be greater than zero, or None.")
    return frame_limit


def read_ats_file(
    path: str,
    preset: Optional[int] = None,
    max_frames: Optional[int] = None,
    object_parameter_updates: Optional[ObjectParameterUpdates] = None,
    read_mode: Optional[str] = None,
    inspection: Optional[ATSInspection] = None,
) -> ATSData:
    imager = fnv.file.ImagerFile(path)
    configure_imager(imager)
    apply_object_parameters(imager, object_parameter_updates)
    frame_limit = _resolve_frame_limit(max_frames)

    if inspection is not None and inspection.path != path:
        raise ValueError(f"Inspection path {inspection.path!r} does not match read path {path!r}.")

    if inspection is None:
        inspection = inspect_ats_file(path, object_parameter_updates=object_parameter_updates)

    available_presets = inspection.available_presets
    preset_value_ranges = inspection.preset_value_ranges
    is_superframing = inspection.is_superframe
    effective_read_mode = _resolve_read_mode(read_mode, preset, is_superframing)

    if preset is not None and preset not in available_presets:
        available = ", ".join(str(value) for value in available_presets) or "none"
        raise ValueError(f"Preset {preset} not available in {path}. Available presets: {available}.")

    if effective_read_mode == "superframe" and not is_superframing:
        raise ValueError("Superframe extraction was requested, but this ATS file is not superframed.")

    frames = []
    timestamps = []
    relative_time = []
    frame_indices = []
    frame_presets = []
    first_timestamp = None
    target_preset = preset

    def append_loaded_frame(frame_index: int) -> None:
        nonlocal first_timestamp

        current_preset = getattr(imager, "preset", None)
        if current_preset is not None:
            current_preset = int(current_preset)

        frame = np.array(imager.final, copy=False).reshape((imager.height, imager.width))
        timestamp = get_timestamp(imager.frame_info)
        if timestamp is None:
            return

        if first_timestamp is None:
            first_timestamp = timestamp

        frames.append(frame.copy())
        timestamps.append(timestamp)
        relative_time.append(timestamp.timestamp() - first_timestamp.timestamp())
        frame_indices.append(frame_index)
        frame_presets.append(-1 if current_preset is None else current_preset)

    if effective_read_mode == "superframe":
        imager.get_superframe(0)
        if imager.preset == 0:
            start_idx = 0
        else:
            start_idx = 1

        if target_preset is None and getattr(imager, "preset", None) is not None:
            target_preset = int(imager.preset)

        for frame_index in range(start_idx, imager.num_frames, 2):
            print("reading frame %d of %d" % (frame_index + 1, imager.num_frames), end="\r")
            imager.get_superframe(frame_index)
            append_loaded_frame(frame_index)
            if frame_limit is not None and len(frames) >= frame_limit:
                break
    else:
        for frame_index in range(imager.num_frames):
            print(f"reading frame {frame_index + 1} of {imager.num_frames}", end="\r")
            _load_frame(imager, frame_index, use_superframe=False)

            current_preset = getattr(imager, "preset", None)
            if current_preset is not None:
                current_preset = int(current_preset)

            if effective_read_mode == "preset" and current_preset != preset:
                continue

            append_loaded_frame(frame_index)
            if frame_limit is not None and len(frames) >= frame_limit:
                break

    print()

    if not frames:
        raise ValueError(f"No frames were read from {path}.")

    return ATSData(
        path=path,
        frames=np.stack(frames, axis=0),
        timestamps=timestamps,
        relative_time=np.asarray(relative_time),
        frame_indices=np.asarray(frame_indices, dtype=int),
        frame_presets=np.asarray(frame_presets, dtype=int),
        preset=target_preset,
        available_presets=available_presets,
        preset_value_ranges=preset_value_ranges,
        is_superframing=is_superframing,
        is_superframe=is_superframing,
        read_mode=effective_read_mode,
        height=imager.height,
        width=imager.width,
    )
