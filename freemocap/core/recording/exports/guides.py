"""Static student-facing guides, staged with scientific exports."""
from pathlib import Path
from freemocap.core.recording.exports.publication import artifact_path

OVERVIEW = """# Exploring FreeMoCap data

These files are analysis-friendly views of a saved processing run. They originate
from camera videos, detector measurements, calibrated triangulation, trajectory
processing, and model-based reconstruction. Parquet in the recording folder is
the canonical scientific result; exports do not rerun those computations.

## What the data represents

| Label | Origin | Components per point or segment |
| --- | --- | --- |
| 2d_overlay | Detector observations in a particular camera image | x, y, confidence |
| 3d_keypoints_raw | Triangulated detector points, before trajectory filtering | x, y, z |
| 3d_keypoints_filtered | Saved processed trajectories; filtering may have been disabled | x, y, z |
| 3d_landmarks | Landmarks reconstructed using the selected anatomical/object model | x, y, z |
| 3d_segment_poses | Reconstructed segment origins and world orientations | x, y, z, qw, qx, qy, qz |

Raw means before trajectory filtering, not before coordinate alignment. Landmarks
are model outputs, not independent measurements of every anatomical location.
2D confidence is the saved detector score (called visibility in Parquet), not
spatial error or a calibrated probability. No reprojection-error or landmark-residual
component is currently appended to these arrays. Joint-angle export is deferred.

## Names, coordinates, and provenance

Names group dimension, data type, processing state, and source; camera files also
include the video basename. `body.nose` is a point in the detector's body stage,
not the tracker name. A tracking stream can currently include ChArUco as well as
human points; producer separation is not yet complete.

2D coordinates use image pixels. Calibrated 3D positions normally use millimeters
and the saved Blender basis (+X right, +Y forward, +Z up). Single-camera planar
outputs use pixels, not millimeters. Always inspect the reference frame and
component units. Quaternions are dimensionless WXYZ, not Euler angles or degrees.
Alignment can use a body anchor when no floor is found; Z=0 is not guaranteed to
be the physical floor. Exporting does not alter units, align, or resample data.

The recording-root `*_recording_info.json` describes the recording. The file with
that suffix here is an export inventory: it links each artifact to its source
hash, run, exact names, components, units, and reference frame. It is the dictionary
for interpreting array axes. Keep it with the exported files when sharing them.
The JSON inside NPZ describes that archive's own snapshot.

## Layout and reuse

`csv/` contains wide tables; `npy/` contains NumPy arrays and shared timing.
An NPZ contains the arrays together in one package. Only selected formats/data
are produced. Each format folder has a loading tutorial below it. All data choices
are optional; 3D landmarks is the default data selection.

Normal exports replace the selected format's prior managed files. Switching
trackers does not automatically retain the old exports. Explicitly kept exports
use `run-<id>/` and run-qualified names. Unselected formats may belong to an older
snapshot: use each artifact's metadata, not folder modification time, as provenance.

## Notebook Explorer

An optional `.ipynb` in the recording folder provides a guided NumPy/Pandas/Plotly
view of the selected Parquet channels. Open it in JupyterLab or VS Code, with its folder as the working
directory. It requires pandas, pyarrow, numpy, and plotly in your analysis
environment; it does not install anything or process videos. Keep the recording
folder layout intact. The notebook verifies its source hash before loading data;
a retained notebook alone does not archive the underlying Parquet file. Save an
edited notebook under a new name to preserve your analysis when regenerating.

## Load an NPZ and plot a landmark

Run from this export folder in an environment with NumPy and Matplotlib. Change
the archive path and landmark name for your recording. This example requires a
3D-landmark export; selecting fewer data products means fewer available channels.

```python
from pathlib import Path
from zipfile import ZipFile
import json
import numpy as np
import matplotlib.pyplot as plt

archive_path = next(Path('.').glob('*.npz'))  # choose explicitly if there are several
with ZipFile(archive_path) as zipped:
    metadata = json.loads(zipped.read('recording_info.json'))
channel = next(c for c in metadata['channels'].values()
               if c['context']['channel'] == 'LANDMARKS_3D')
with np.load(archive_path, allow_pickle=False) as archive:
    values = archive[channel['numpy_key'] + '.values']
    times = archive['timestamps']
    frames = archive['frames']
print(channel['names'])
name = channel['names'][0]  # replace with a name from the printed list
j = channel['names'].index(name)
k = channel['components'].index('x')
assert len(values) == len(times) == len(frames)
plt.plot(times - times[0], values[:, j, k])
plt.xlabel('Elapsed time (s)')
plt.ylabel('X position (' + channel['units'][k] + ')')
plt.title(name)
plt.show()
```

NaNs become gaps in the plot. Do not turn missing points into zeros: that invents
positions. Use actual timestamps rather than assuming a frame rate.
"""

CSV = """# Reading wide CSV tables

Run the example from this `csv` folder. Each row is a saved frame, beginning with
`frame_number` and `timestamp_s`. Remaining columns are `point.component`, for
example `body.nose.x` or `pelvis.qw`. Names can contain periods: the last period
separates the component in current scientific exports. Ordinary CSV quoting handles
commas and quotes; there is no URL decoding step.

Columns follow the recorded name/component order. Large tables can be split into
row or column parts: one part is not the complete channel. Use `frame_slice` and
`value_column_slice` in the parent export inventory to identify the parts. Join
column parts by frame_number and verify their timestamps; concatenate row parts
in frame order. Never concatenate unrelated camera or model tables.

An empty field means the source entry was absent; `NaN` means an explicitly missing
value. Pandas normally reads both as NaN, which is convenient for analysis but loses
that distinction. Use `keep_default_na=False` if you need the original text.
2D tables contain pixel x/y and dimensionless confidence; 3D position units are
in the parent inventory. See the parent README for provenance and coordinates.

```python
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

path = next(Path('.').glob('*.3d_landmarks--*.csv'))  # choose your table explicitly
# utf-8-sig also handles the Unicode byte-order mark used for spreadsheet tools.
table = pd.read_csv(path, encoding='utf-8-sig')
print(table.columns.tolist())
column = next(c for c in table.columns if c.endswith('.x'))
plt.plot(table['timestamp_s'] - table['timestamp_s'].iloc[0], table[column])
plt.xlabel('Elapsed time (s)')
plt.ylabel('X position (recorded units; see export inventory)')
plt.title(column)
plt.show()
```

This plots one coordinate of one landmark, not the full skeleton. To inspect
missing values, use `table[column].isna()`. Choose a different named column to
compare landmarks or coordinates. Do not plot confidence as if it were distance.
"""

NPY = """# Reading NumPy arrays

Each measurement file has axes `(frames, names, components)`. 3D points use XYZ,
2D points use XY/confidence, and segment poses use XYZ/QW/QX/QY/QZ. The ordering
of names and components is in the parent export inventory; never assume that
point index 0 means the same landmark for different detectors.

One shared `.frames.npy` (integer frame identifiers) and `.timestamps.npy` (seconds)
serve this export set. Measurement arrays are float64. Every selected measurement
array must share the frame grid; export checks counts, frame IDs and timestamps.
The first array index is a row index, not necessarily the recorded frame number.
Missing coordinates are NaN. There are no `.present.npy` arrays. Use
`np.isfinite(values[..., :3]).all(axis=-1)` for complete XYZ points, or `:2` for XY.
Confidence zero is a score, not automatically a valid coordinate or a missing flag.

Run this example from `npy/`, with NumPy and Matplotlib available. It selects a
landmark array through metadata, so its names, units, and timing stay associated.

```python
from pathlib import Path
import json
import numpy as np
import matplotlib.pyplot as plt

root = Path('..')
metadata_path = next(root.glob('*_recording_info.json'))
manifest = json.loads(metadata_path.read_text(encoding='utf-8'))
for artifact in manifest['artifacts'].values():
    if artifact['format'] != 'npy' or artifact['details']['role'] != 'values':
        continue
    snapshot = manifest['snapshots'][artifact['source_sha256']]
    channel = snapshot['channels'][artifact['details']['context_key']]
    if channel['context']['channel'] == 'LANDMARKS_3D':
        break
else:
    raise ValueError('Export 3D landmarks as NPY first')
values = np.load(root / artifact['filename'], allow_pickle=False)
times = np.load(root / snapshot['numpy_timeline']['timestamps_file'], allow_pickle=False)
frames = np.load(root / snapshot['numpy_timeline']['frames_file'], allow_pickle=False)
assert values.shape[0] == len(times) == len(frames)
print(channel['names'], channel['components'])
name = channel['names'][0]  # select a landmark by its recorded name
j = channel['names'].index(name)
k = channel['components'].index('x')
plt.plot(times - times[0], values[:, j, k])
plt.xlabel('Elapsed time (s)')
plt.ylabel('X position (' + channel['units'][k] + ')')
plt.title(name)
plt.show()
```

Keep timestamps in seconds when differentiating positions into velocities.
Consider missing samples and noise before computing derivatives; this example
only plots saved positions. NPZ contains the same arrays in a zip package; see
the parent README for a loading example.
"""


def stage_guides(directory: Path, staging: Path, formats) -> tuple[str, ...]:
    guides = {'README.md': OVERVIEW}
    if 'wide_csv' in formats:
        guides['csv/README.md'] = CSV
    if 'npy' in formats:
        guides['npy/README.md'] = NPY
    written = []
    for name, content in guides.items():
        # Preserve existing tutorials, including a student's annotations.
        if artifact_path(directory, name).exists():
            continue
        path = artifact_path(staging, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
        written.append(name)
    return tuple(written)
