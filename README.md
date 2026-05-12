# ats-utils

Utilities for opening, reading, exporting, and visualizing thermal videos in FLIR ATS format.

The maintained workflow lives in `ats_temperature_basic/`. The `FLIR examples/` folder is kept separately with the original example-style scripts adapted from FLIR SDK workflows.

## Repository Structure

```text
ats-utils/
  README.md
  LICENSE
  environment.yaml
  ats_temperature_basic/
    object_parameters.json
    ats_reader.py
    example_read_ats.py
    batch_import_ats_superframe_processing_visualization.ipynb
    temperature_exploration.py
  FLIR examples/
    min_and_max.py
    print_metadata.py
```

Generated outputs are ignored by git:

- `ats_temperature_basic/exported_frames/`
- `ats_temperature_basic/intensity_statistics_csv/`

## Requirements

For `ats_temperature_basic/ats_reader.py`, the Python package requirements are:

- `numpy`
- FLIR Science File SDK for Python, imported as `fnv`

The FLIR Science File SDK is not treated here as a normal conda/pip dependency. Install it by following the FLIR/Teledyne instructions. A FLIR support login is required to access the SDK download:

https://flir.custhelp.com/app/answers/detail/a_id/3504/~/flir-science-file-sdk-for-python---getting-started

## Command-Line Usage

Run the basic reader interactively:

```bash
cd ats_temperature_basic
python example_read_ats.py /path/to/video.ats
```

Run non-interactively:

```bash
python example_read_ats.py /path/to/video.ats --export 0 --preset-gap keep
python example_read_ats.py /path/to/video.ats --export all-presets
python example_read_ats.py /path/to/video.ats --export superframe --preset-gap nan
```

By default the CLI loads object parameters from:

```text
ats_temperature_basic/object_parameters.json
```

Use another config file when needed:

```bash
python example_read_ats.py /path/to/video.ats \
  --object-parameters-config /path/to/object_parameters.json \
  --export superframe
```

You can still override individual config values for one run:

```bash
python example_read_ats.py /path/to/video.ats \
  --export superframe \
  --emissivity 0.95 \
  --reflected-temperature-k 293.15 \
  --object-distance-m 1.0 \
  --atmospheric-temperature-k 293.15 \
  --relative-humidity 0.50
```

Fractions use `0..1` notation, not percentages. Temperatures are Kelvin.

## Notebook Usage

Open:

```text
ats_temperature_basic/batch_import_ats_superframe_processing_visualization.ipynb
```

Edit the first cell to set:

- `ATS_FOLDER`: folder containing `.ats` files.
- `CODE_DIR`: folder containing `ats_reader.py`.
- `OBJECT_PARAMETERS_CONFIG`: reusable JSON config for object parameters.
- `MAX_FILES`: optional limit while testing.
- `MAX_FRAMES_PER_VIDEO`: optional limit on output superframes.

The notebook imports data with `list_ats_files()`, `inspect_ats_file()`, and `read_ats_file()`. Notebook-specific analysis helpers, such as layer sorting and statistics tables, stay inside the notebook.

## Library Usage

```python
from ats_reader import (
    inspect_ats_file,
    load_object_parameter_updates,
    read_ats_file,
)

ats_path = "/path/to/video.ats"

object_parameters = load_object_parameter_updates("object_parameters.json")

inspection = inspect_ats_file(
    ats_path,
    object_parameter_updates=object_parameters,
    collect_preset_value_ranges=False,
)

data = read_ats_file(
    ats_path,
    read_mode="superframe",
    max_frames=None,
    object_parameter_updates=object_parameters,
    inspection=inspection,
)

frames = data.frames
relative_time = data.relative_time
```

`read_mode` can be:

- `preset`: read only frames matching `preset=<number>`.
- `all_presets`: read all raw preset frames.
- `superframe`: call `get_superframe()` and read reconstructed superframes when the file supports superframing.

Use `max_frames=<number>` to stop after that many output frames. In `read_mode="superframe"`, this means output superframes.

## Object Parameters

Object parameters must be applied before frames are read because the FLIR SDK uses them while converting radiometric data to temperatures. The reader defaults to `emissivity=1.0`; pass the other values when your measurement setup needs them.

The reusable config lives at `ats_temperature_basic/object_parameters.json`:

```json
{
  "emissivity": 1.0,
  "reflected_temperature": null,
  "object_distance": null,
  "atmospheric_temperature": null,
  "relative_humidity": null,
  "atmospheric_transmission": null,
  "external_optics_temperature": null,
  "external_optics_transmission": null
}
```

Use `null` for optional values that should not be applied as explicit object-parameter updates.

| Reader name | Expected value | When to set it |
| --- | --- | --- |
| `emissivity` | Fraction from `0` to `1` | Set for every temperature read. Use `1.0` for blackbody-like calibrated data. |
| `reflected_temperature` | Kelvin | Set when emissivity is below `1.0` or the surroundings differ from the target. |
| `object_distance` | Meters | Set when the object-camera distance is known, especially for longer paths. |
| `atmospheric_temperature` | Kelvin | Set when atmospheric compensation matters for the measurement setup. |
| `relative_humidity` | Fraction from `0` to `1` | Set when atmospheric compensation matters. Use `0.50` for 50%. |
| `atmospheric_transmission` | Fraction from `0` to `1` | Set only when you want to override the SDK/camera transmission estimate. |
| `external_optics_temperature` | Kelvin | Set when an external lens, IR window, or heat shield is in the optical path. |
| `external_optics_transmission` | Fraction from `0` to `1` | Set when external optics are in the optical path. Use `1.0` when absent. |

Not every SDK build or file exposes every object-parameter attribute. If a name is unsupported, `apply_object_parameters()` raises an error listing the names exposed by the installed SDK for that file.

## Exported `.npz` Contents

`example_read_ats.py` writes a compressed NumPy file containing:

- `frames`: temperature stack shaped `(frames, rows, columns)`.
- `relative_time`: seconds from the first valid frame.
- `frame_indices`: original ATS frame indices that were read.
- `frame_presets`: preset number per frame, or `-1` when unknown.
- `timestamps_utc`: ISO-formatted UTC timestamps from frame metadata.
- `source_path`, `export_selection`, `read_mode`, `preset_gap_action`: provenance for the export.
- `preset_gap_bounds`: ranges that can be masked for superframes.
- `available_presets` and `preset_value_range_*`: observed preset metadata.
- `object_parameter_names` and `object_parameter_values`: object parameters applied before reading.
- `emissivity`: kept as a convenience value for older scripts.

Load an export like this:

```python
import numpy as np

with np.load("exported_frames/video_superframe_gap_nan.npz") as exported:
    frames = exported["frames"]
    time_s = exported["relative_time"]
```

## Function Reference

### `ats_reader.py`

- `ATSObjectParameters`: dataclass for supported object-parameter names.
- `build_object_parameter_updates()`: validates object-parameter values.
- `build_object_parameter_updates_from_mapping()`: validates object-parameter values loaded from mappings such as JSON.
- `load_object_parameter_updates()`: loads and validates `object_parameters.json`.
- `list_ats_files()`: lists `.ats` files in a folder, skipping macOS resource-fork files.
- `inspect_ats_file()`: opens an ATS file, applies object parameters, detects presets, and returns `ATSInspection`.
- `read_ats_file()`: reads selected frames into an `ATSData` object.
- `get_timestamp()`: converts FLIR frame `Time` metadata to UTC `datetime`.
- `apply_object_parameters()`: applies object parameters to `imager.object_parameters`.
- `configure_imager()`: selects factory temperature in Kelvin when available, otherwise counts.

### `temperature_exploration.py`

- `preset_ranges_overlap()`: returns `True` when adjacent preset temperature ranges overlap.
- `get_preset_gap_bounds()`: finds temperature gaps between adjacent preset ranges.
- `mask_temperatures_between_presets()`: replaces values inside preset gaps with `NaN`.
- `extract_temperature_histories()`: extracts mean temperature histories around `(x, y)` coordinates.

### `example_read_ats.py`

Provides the command-line workflow for inspecting an ATS file, choosing an export mode, saving frames, and printing summary statistics.

### Notebook

`batch_import_ats_superframe_processing_visualization.ipynb` provides an interactive batch workflow for loading superframes, computing notebook-specific statistics, exporting CSV summaries, plotting, and ROI visualization.
