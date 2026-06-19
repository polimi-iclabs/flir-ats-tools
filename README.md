# flir-ats-tools: Python tools for FLIR ATS thermal video files

Utilities for opening, reading, exporting, and analyzing thermal videos in FLIR ATS format.

The installable Python package is `flir_ats_tools`. Reader and SDK helpers live under `flir_ats_tools.utilities`; temperature-analysis helpers live under `flir_ats_tools.analysis`. The `FLIR examples/` folder is kept separately with the original example-style scripts adapted from FLIR SDK workflows.

## Repository Structure

```text
flir-ats-tools/
  pyproject.toml
  setup.cfg
  setup.py
  README.md
  LICENSE
  flir_ats_tools/
    __init__.py
    cli.py
    utilities/
      __init__.py
      ats_reader.py
      object_parameters.json
    analysis/
      __init__.py
      temperature.py
  notebooks/
    batch_import_ats_superframe_processing_visualization.ipynb
    batch_import_ats_superframe_processing_visualization_v2.ipynb
  FLIR examples/
    min_and_max.py
    print_metadata.py
```

Generated outputs are ignored by git:

- `exported_frames/`
- `intensity_statistics_csv/`
- `notebooks/exported_frames/`
- `notebooks/intensity_statistics_csv/`

## Requirements

For `flir_ats_tools.utilities.ats_reader`, the Python package requirements are:

- `numpy`
- FLIR Science File SDK for Python, imported as `fnv`

The FLIR Science File SDK is not treated here as a normal conda/pip dependency. Install it by following the FLIR/Teledyne instructions. A FLIR support login is required to access the SDK download:

https://flir.custhelp.com/app/answers/detail/a_id/3504/~/flir-science-file-sdk-for-python---getting-started

## Installation

Install this repository as a local editable package from the repository root:

```bash
python -m pip install -e .
```

The editable install exposes the `flir_ats_tools` package and installs the `flir-ats-read` command-line script. The package includes the default `object_parameters.json` config file.

## Command-Line Usage

After installing the package, run the reader interactively:

```bash
flir-ats-read /path/to/video.ats
```

Run the same CLI directly from the source tree when needed:

```bash
python -m flir_ats_tools.cli /path/to/video.ats
```

Run non-interactively:

```bash
flir-ats-read /path/to/video.ats --export 0 --preset-gap keep
flir-ats-read /path/to/video.ats --export all-presets
flir-ats-read /path/to/video.ats --export superframe --preset-gap nan
```

By default the CLI loads object parameters from the package config:

```text
flir_ats_tools/utilities/object_parameters.json
```

Use another config file when needed:

```bash
flir-ats-read /path/to/video.ats \
  --object-parameters-config /path/to/object_parameters.json \
  --export superframe
```

You can still override individual config values for one run:

```bash
flir-ats-read /path/to/video.ats \
  --export superframe \
  --emissivity 0.95 \
  --reflected-temp-k 293.15 \
  --distance-m 1.0 \
  --atmosphere-temp-k 293.15 \
  --relative-humidity 0.50
```

Fractions use `0..1` notation, not percentages. Temperatures are Kelvin.

## Notebook Usage

Open:

```text
notebooks/batch_import_ats_superframe_processing_visualization.ipynb
```

Edit the first cell to set:

- `ATS_FOLDER`: folder containing `.ats` files.
- `OBJECT_PARAMETERS_CONFIG`: reusable JSON config for object parameters.
- `MAX_FILES`: optional limit while testing.
- `MAX_FRAMES_PER_VIDEO`: optional limit on output superframes.

The notebook imports data with `list_ats_files()`, `inspect_ats_file()`, and `read_ats_file()` from `flir_ats_tools.utilities`. Notebook-specific analysis helpers, such as layer sorting and statistics tables, stay inside the notebook.

## Library Usage

```python
from flir_ats_tools.utilities import (
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

Analysis helpers are available separately:

```python
from flir_ats_tools.analysis import (
    extract_temperature_histories,
    get_preset_gap_bounds,
    mask_temperatures_between_presets,
)
```

`read_mode` can be:

- `preset`: read only frames matching `preset=<number>`.
- `all_presets`: read all raw preset frames.
- `superframe`: call `get_superframe()` and read reconstructed superframes when the file supports superframing.

Use `max_frames=<number>` to stop after that many output frames. In `read_mode="superframe"`, this means output superframes.

## Object Parameters

Object parameters must be applied before frames are read because the FLIR SDK uses them while converting radiometric data to temperatures. The reader defaults to `emissivity=1.0`; pass the other values when your measurement setup needs them.

The reusable config lives at `flir_ats_tools/utilities/object_parameters.json`:

```json
{
  "atmosphere_temp": null,
  "atmospheric_transmission": null,
  "distance": null,
  "emissivity": null,
  "est_atmospheric_transmission": null,
  "ext_optics_temp": null,
  "ext_optics_transmission": null,
  "reflected_temp": null,
  "relative_humidity": null,
  "source": null
}
```

Use `null` for values that should not be applied as explicit object-parameter updates.

| Reader name | Expected value | When to set it |
| --- | --- | --- |
| `emissivity` | Fraction from `0` to `1` | Set for every temperature read. Use `1.0` for blackbody-like calibrated data. |
| `reflected_temp` | Kelvin | Set when emissivity is below `1.0` or the surroundings differ from the target. |
| `distance` | Meters | Set when the object-camera distance is known, especially for longer paths. |
| `atmosphere_temp` | Kelvin | Set when atmospheric compensation matters for the measurement setup. |
| `relative_humidity` | Fraction from `0` to `1` | Set when atmospheric compensation matters. Use `0.50` for 50%. |
| `atmospheric_transmission` | Fraction from `0` to `1` | Set only when you want to override the SDK/camera transmission estimate. |
| `est_atmospheric_transmission` | Boolean | Set when you want the SDK to estimate atmospheric transmission. |
| `ext_optics_temp` | Kelvin | Set when an external lens, IR window, or heat shield is in the optical path. |
| `ext_optics_transmission` | Fraction from `0` to `1` | Set when external optics are in the optical path. Use `1.0` when absent. |
| `source` | Value accepted by the FLIR SDK | Leave unset unless your camera setup requires an explicit source parameter. |

Not every SDK build or file exposes every object-parameter attribute. If a name is unsupported, `apply_object_parameters()` raises an error listing the names exposed by the installed SDK for that file.

## Exported `.npz` Contents

`flir-ats-read` writes a compressed NumPy file containing:

- `frames`: temperature stack shaped `(frames, rows, columns)`.
- `relative_time`: seconds from the first valid frame.
- `frame_indices`: original ATS frame indices that were read.
- `frame_presets`: preset number per frame, or `-1` when unknown.
- `timestamps_utc`: ISO-formatted UTC timestamps from frame metadata.
- `source_path`, `export_selection`, `read_mode`, `preset_gap_action`: provenance for the export.
- `preset_gap_bounds`: ranges that can be masked for superframes.
- `available_presets` and `preset_value_range_*`: observed preset metadata.
- `object_parameter_names` and `object_parameter_values_json`: object parameters applied before reading.
- `emissivity`: kept as a convenience value for older scripts.

Load an export like this:

```python
import numpy as np

with np.load("exported_frames/video_superframe_gap_nan.npz") as exported:
    frames = exported["frames"]
    time_s = exported["relative_time"]
```

## Function Reference

### `flir_ats_tools.utilities`

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

### `flir_ats_tools.analysis`

- `preset_ranges_overlap()`: returns `True` when adjacent preset temperature ranges overlap.
- `get_preset_gap_bounds()`: finds temperature gaps between adjacent preset ranges.
- `mask_temperatures_between_presets()`: replaces values inside preset gaps with `NaN`.
- `extract_temperature_histories()`: extracts mean temperature histories around `(x, y)` coordinates.

### `flir_ats_tools.cli`

Provides the command-line workflow for inspecting an ATS file, choosing an export mode, saving frames, and printing summary statistics.

### Notebook

`notebooks/batch_import_ats_superframe_processing_visualization.ipynb` provides an interactive batch workflow for loading superframes, computing notebook-specific statistics, exporting CSV summaries, plotting, and ROI visualization.
