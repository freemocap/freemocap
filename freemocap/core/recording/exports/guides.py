"""Executable student guides for scientific arrays, tables and runtime objects."""
import hashlib
from pathlib import Path
from textwrap import indent

from freemocap.core.recording.exports.publication import artifact_path


_CHANNEL_READ = """channel = next(item for item in manifest['channels']
               if item['storage_kind'] == 'time_series'
               and item['tensor_layout']['channel_kind'] == 'LANDMARKS_3D')
layout = channel['tensor_layout']
timing = next(item for item in manifest['timings'] if item['timing_key'] == channel['timing_ref'])
values = read_array(channel['values_file'])
frames = read_array(timing['sample_ids_file'])
times = read_array(timing['timestamps_s_file'])
axis_names = [axis['axis_name'] for axis in layout['axes']]
entity_axis = axis_names.index('entity_identity')
component_axis = axis_names.index('component_identity')
names = layout['axes'][entity_axis]['identifiers']
components = layout['axes'][component_axis]['identifiers']
name, component_name = names[0], components[0]  # choose declared names here
indices = [slice(None)] * values.ndim
indices[entity_axis] = names.index(name)
indices[component_axis] = components.index(component_name)
trajectory_values = values[tuple(indices)]
for companion in channel['companion_tensors']:
    if companion['metadata_name'] in ('entry_presence', 'value_validity'):
        selected_mask = read_array(companion['values_file'])[tuple(indices)]
        trajectory_values = np.where(selected_mask, trajectory_values, np.nan)
assert trajectory_values.shape == times.shape == frames.shape
"""

_PLOT_CHANNEL = """if not len(times):
    raise ValueError('The selected channel has no samples')
plt.plot(times - times[0], trajectory_values)
plt.xlabel('Elapsed time (s)')
plt.ylabel(component_name + ' (' + layout['component_units'][components.index(component_name)] + ')')
plt.title(name)
plt.show()
"""

OVERVIEW = """# Exploring FreeMoCap data

Parquet is the primary durable recording. CSV, NPY and NPZ expose selected
scientific outputs without rerunning detection or reconstruction. Detector estimates,
triangulated positions and model predictions have different meanings; reconstructed
landmarks are not independent empirical measurements of every anatomical location.

## Choose a representation

- `csv/` contains wide spreadsheet tables. Spatial columns use canonical coordinate
  order; overlays call the saved visibility score `confidence`. Segment-pose tables
  combine segment origins and world quaternion components for convenience.
- `npy/` contains `dataset.json` and ordinary numerical `.npy` files. The manifest
  declares each tensor's axes, component names, units, source and timing reference.
- NPZ packages the same dataset manifest and numerical files into one archive.
  NumPy preserves authored component labels, including `visibility`; segment poses
  remain the runtime `SEGMENT_ORIGINS` and `ROTATIONS_WORLD` channels.

The component count comes from each declared layout. Channel sample counts, frame
IDs and timestamps can differ. Follow each channel's `timing_ref`; never substitute
another channel's timestamps because the lengths happen to match. Static fitted
scales and lengths have no invented frame axis. Their measured/voting support arrays
identify which segments supplied fitting evidence.

`entry_presence` distinguishes an absent entry from a recorded null. A present row
can still contain NaN. Presence is not a confidence score or proof of scientific
validity. Optional `value_validity` and quality/evidence companions have their own
names and declared layouts. Saved Parquet currently provides row presence, not an
independent validity mask; the export does not invent one. Keep unavailable values
as missing, rather than replacing them with zero.

Use the recorded units and reference definitions. Calibrated spatial positions
usually use millimeters; planar results may use pixels. World orientation uses
WXYZ quaternions. No export aligns, filters, synchronizes or resamples values.

## Recording runs and published files

Normal processing overwrites the selected run (run 0 by default). Creating a new
run is an explicit processing choice; exporting does not allocate runs. Run 0
normally uses `exports/`; nonzero runs and explicitly kept exports use `run-<id>/`.
Repeating a normal NPY export replaces that run's managed `npy/` dataset, including
obsolete managed arrays. Unrelated or edited files are protected. CSV's current
inventory names its selected tables; older unselected CSV files may remain on disk.

The outer `*_recording_info.json` inventory records hashes, source revision and
run. Each snapshot's `numpy_datasets` describes NPY and NPZ separately, including
paths, selection and whether values came from a caller-supplied runtime dataset.
An unselected format can retain an older selection or source revision. Use its
own descriptor. Inside NPY/NPZ, `dataset.json` is sufficient to interpret that
scientific dataset without the original Parquet or the outer export inventory.

## Load an NPZ with plain NumPy

Run this example from the export directory with NumPy and Matplotlib available.
Select an archive containing a LANDMARKS_3D channel; replace the first declared
entity/component below to plot another trajectory. No FreeMoCap or SkellyForge
import is required.

```python
from pathlib import Path
from zipfile import ZipFile
import json
import numpy as np
import matplotlib.pyplot as plt

archive_path = next(Path('.').glob('*.npz'))  # choose explicitly when several exist
with ZipFile(archive_path) as archive:
    manifest = json.loads(archive.read('dataset.json'))
    def read_array(filename):
        with archive.open(filename) as member:
            return np.load(member, allow_pickle=False)
""" + indent(_CHANNEL_READ, '    ') + _PLOT_CHANNEL + """```

NaNs create gaps in the plot. Use actual timestamps when calculating derivatives.
See `npy/README.md` for standalone NPY loading and Forge runtime-object helpers.

## Notebook Explorer

The optional notebook beside the recording Parquet explores the selected display
products through Polars and NumPy, with Plotly coordinate plots and 3D playback.
It checks the source hash and uses that channel's saved timing. It does not add
NumPy's static fits to the trajectory selector. Execution needs numpy,
polars>=2,<3 and plotly>=6,<7; there are no installation cells. Keep the recording
layout intact, and save edited notebooks under another name before regenerating.
"""

CSV = """# Reading wide CSV tables

Run the example from this `csv` folder. Dynamic tables have one row per saved frame, beginning with
`frame_number` and `timestamp_s`. Remaining columns are `point.component`, for
example `body.nose.x` or `pelvis.qw`. Names can contain periods: the last period
separates the component in current scientific exports. Ordinary CSV quoting handles
commas and quotes; there is no URL decoding step.

Names follow the recorded order. Spatial CSV components use canonical XYZ or WXYZ order; combined segment-pose tables append quaternion components. Other components follow their declared order. Large tables can be split into
row or column parts: one part is not the complete channel. Use `frame_slice` and
`value_column_slice` in the parent export inventory to identify the parts. Join
column parts by frame_number and verify their timestamps; concatenate row parts
in frame order. Never concatenate unrelated camera or model tables.

Static fit tables contain one row of named values and no frame or timestamp columns.

An empty field means the source entry was absent; `NaN` means an explicitly missing
value. Polars preserves empty numeric fields as null and explicit `NaN` as NaN.
Inspect them with `is_null()` and `is_nan()` before converting to NumPy for plotting.
2D tables contain pixel x/y and dimensionless confidence; 3D position units are
in the parent inventory. See the parent README for provenance and coordinates.

```python
from pathlib import Path
import polars as pl
import matplotlib.pyplot as plt

path = next(Path('.').glob('*.3d_landmarks--*.csv'))  # choose your table explicitly
# Polars reads the UTF-8 byte-order mark used by the spreadsheet export.
csv_query = pl.scan_csv(path)
print(csv_query.collect_schema().names())
column = next(c for c in csv_query.collect_schema().names() if c.endswith('.x'))
table = csv_query.select(pl.col('timestamp_s').cast(pl.Float64),
                         pl.col(column).cast(pl.Float64)).collect()
plt.plot(table['timestamp_s'].to_numpy() - table['timestamp_s'][0], table[column].to_numpy())
plt.xlabel('Elapsed time (s)')
plt.ylabel('X position (recorded units; see export inventory)')
plt.title(column)
plt.show()
```

This plots one coordinate of one landmark, not the full skeleton. To inspect
missing values, use `table[column].is_null()` and `table[column].is_nan()`. Choose a different named column to
compare landmarks or coordinates. Do not plot confidence as if it were distance.
"""

NPY = """# Reading NumPy datasets

This folder is a standalone scientific dataset: `dataset.json` describes its
numerical `.npy` files. Channels compose dense values, explicit axes, provenance
and companion arrays. A time series additionally identifies its sample axis and
an entry in the timing registry. Other channels are static tensors. No common
frame count, fixed component width or hardware clock synchronization is assumed.

Names and components follow the runtime layout, including `visibility` for
saved detector scores. Origins and world rotations remain separate channels.
Each layout supplies units and coordinate references. Definition documents carry
selected model, reference and scientific source settings. Execution status and
solver caches are excluded. Use companions to preserve missingness and evidence;
finite values alone are not an independent validity or quality declaration.

## Load and plot with plain NumPy

Run from this `npy/` folder with NumPy and Matplotlib installed. This example
selects a landmark time series and its own sample IDs and timestamps. Optional
memory mapping is available for plain NPY users; close those maps when finished.

```python
from pathlib import Path
import json
import numpy as np
import matplotlib.pyplot as plt

directory = Path('.')
manifest = json.loads((directory / 'dataset.json').read_text(encoding='utf-8'))
def read_array(filename):
    return np.load(directory / filename, allow_pickle=False)
""" + _CHANNEL_READ + _PLOT_CHANNEL + """```

## Load the same runtime objects with SkellyForge

With SkellyForge installed, its loader validates the manifest and returns owned,
immutable arrays in the same `RecordingDataset`, `TimeSeries` and `DataTensor`
objects used by the application. It accepts this NPY directory or an NPZ archive.
Neither loading nor saving needs FreeMoCap, SkellyTracker or the original Parquet.
Use a fresh destination for a standalone save; the helper does not overwrite files.

```python
from pathlib import Path
from skellyforge.core.data_tensors import RecordingDataset

dataset = RecordingDataset.load_numpy(Path('.'))  # an NPZ path works here too
series = next(item for item in dataset.time_series
              if item.data_tensor.tensor_layout.channel_kind == 'LANDMARKS_3D')
values = series.data_tensor.data_values
frames = series.sample_timing.sample_ids
times = series.sample_timing.timestamps_s
layout = series.data_tensor.tensor_layout
# This explicit copy destination must not already exist.
dataset.save_numpy(Path('../analysis_copy.npz'), format='npz')
restored = RecordingDataset.load_numpy(Path('../analysis_copy.npz'))
assert restored.channel_identities == dataset.channel_identities
```

FreeMoCap's saved-result export still reads selected Parquet channels to assemble
these objects. Its `runtime_dataset` entry point can write already selected runtime
arrays directly for NPY/NPZ. Wide CSV and notebooks continue to use saved results.
"""

# Exact previously generated guides, in Windows and LF encodings. Unknown or
# annotated documents are never overwritten by automatic guide refresh.
PREVIOUS_GUIDE_HASHES = {
    'README.md': {'ca700e942eb671851c74c3ed68b23eb1b746b3568d152ce1a0e9e08fd1a57313',
                  '26c3a86c02c3687a186cef151d350c07d3728840edcb765b6b30fd31c95c5de6'},
    'csv/README.md': {'b39b6ba813ff036a8c82d958ed1f2f4fb65b0625f822df85d34bd6985b2ffe36',
                      '7a59bdde48c36eb450c79743a6f1661f94b68d5c0258fb5ef4a30e5ffae575e3'},
    'npy/README.md': {'1667b502b5806a6105706e8af78144d6cef71e37af9d0ab3a542af4451b872e9',
                      '1557ecb8543e6700dac41c82c2e5a7d10d4cde35e837b1d7e83a182067eb0515'},
}


def stage_guides(directory: Path, staging: Path, formats, *, keep=False) -> tuple[str, ...]:
    guides = {'README.md': OVERVIEW}
    if 'wide_csv' in formats:
        guides['csv/README.md'] = CSV
    if 'npy' in formats:
        guides['npy/README.md'] = NPY
    written = []
    for name, content in guides.items():
        existing = artifact_path(directory, name)
        if existing.exists() and (keep or hashlib.sha256(existing.read_bytes()).hexdigest() not in PREVIOUS_GUIDE_HASHES[name]):
            continue
        path = artifact_path(staging, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
        written.append(name)
    return tuple(written)
