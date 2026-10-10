"""Generate an unexecuted, portable Pandas/Matplotlib recording explorer."""
import json
from pathlib import Path

LOAD = r"""from pathlib import Path
import hashlib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# Start Jupyter in the notebook's folder, or set this path explicitly.
parquet_path = Path(SOURCE_PATH)
if not parquet_path.is_file():
    raise FileNotFoundError(f"Keep this notebook with its recording, or update parquet_path: {parquet_path}")
with parquet_path.open('rb') as stream:
    actual_hash = hashlib.file_digest(stream, 'sha256').hexdigest()
if actual_hash != SOURCE_HASH:
    raise ValueError('The recording changed after this notebook was exported. Export a new explorer for the new result.')
print('Selected run:', RUN_ID)
for index, channel in enumerate(CHANNELS):
    print(index, channel['context']['channel'], channel['context']['source'],
          channel['context']['reference_frame'])
"""

TABLE = r"""# Choose an index from the channel list above.
channel_index = 0
channel = CHANNELS[channel_index]
context = channel['context']

def read_channel(kind):
    filters = [('run_id', '=', RUN_ID), ('sensor_group', '=', context['sensor_group']),
               ('source', '=', context['source']), ('channel', '=', kind)]
    rows = pd.read_parquet(parquet_path, filters=filters,
                           columns=['frame_number', 'timestamp_s', 'reference_frame', 'name', 'component', 'value'])
    reference = context['reference_frame']
    rows = rows[rows.reference_frame.isna() if reference is None else rows.reference_frame.eq(reference)].copy()
    return rows

if context['channel'] == 'SEGMENT_POSES':
    positions = read_channel('SEGMENT_ORIGINS')
    rotations = read_channel('ROTATIONS_WORLD')
    rotations['component'] = 'q' + rotations['component']
    rows = pd.concat([positions, rotations], ignore_index=True)
else:
    rows = read_channel(context['channel'])
    if context['channel'] == 'OVERLAY_2D':
        rows['component'] = rows['component'].replace({'visibility': 'confidence'})
if rows.empty:
    raise ValueError('No saved samples for this channel')
clock = rows.groupby('frame_number')['timestamp_s'].agg(['first', 'min', 'max']).sort_index()
# Match the exporter's allowance for floating-point timestamp roundoff.
tolerance = 4 * np.abs(np.spacing(clock['first'].to_numpy()))
if np.any((clock['max'] - clock['first']).to_numpy() > tolerance) or np.any((clock['first'] - clock['min']).to_numpy() > tolerance):
    raise ValueError('Conflicting timestamps in the selected channel')
times = clock['first']
columns = pd.MultiIndex.from_product([channel['names'], channel['components']], names=['name', 'component'])
table = rows.pivot(index='frame_number', columns=['name', 'component'], values='value')
table = table.reindex(index=times.index, columns=columns)
values = table.to_numpy(dtype=float).reshape(len(table), len(channel['names']), len(channel['components']))
print('Array axes: frames, names, components; shape:', values.shape)
print('Components:', dict(zip(channel['components'], channel['units'])))
table.head()
"""

PLOT = r"""# Choose a name and component from the printed metadata, not a hardcoded point index.
name = channel['names'][0]
component = channel['components'][0]
unit = channel['units'][channel['components'].index(component)]
plt.figure(figsize=(10, 4))
plt.plot(times.to_numpy() - times.iloc[0], table[(name, component)].to_numpy())
plt.xlabel('Elapsed time (s)')
plt.ylabel(f'{component} ({unit})')
plt.title(f"{context['source']}: {name}")
plt.tight_layout()
plt.show()
"""


def write_notebook(path: Path, *, snapshot: dict, retained: bool) -> None:
    def cell(kind, source):
        result = dict(cell_type=kind, metadata={}, source=source.splitlines(keepends=True))
        if kind == 'code':
            result.update(execution_count=None, outputs=[])
        return result
    source_path = ('../../' if retained else '../') + snapshot['source_file']
    setup = ('import json\n' +
        f'SOURCE_PATH = {source_path!r}\nSOURCE_HASH = {snapshot["source_sha256"]!r}\nRUN_ID = {snapshot["run_id"]!r}\n' +
        'CHANNELS = json.loads(' + repr(json.dumps(list(snapshot['channels'].values()))) + ')\n')
    cells = [cell('markdown', """# FreeMoCap Notebook Explorer

A guided view of your selected saved run. This notebook follows the V1 explorer
idea using V2 Parquet, explicit channel metadata, Pandas, NumPy, and Matplotlib.
It does not rerun video tracking or alter recording files.

Use Python 3.11 or newer with pandas, pyarrow, numpy, and matplotlib installed in
your Jupyter/VS Code analysis environment. No automatic installs are performed.
Keep this notebook in its export folder with the recording folder structure intact.
The first step checks that the Parquet file still matches the exported snapshot.
A retained notebook is not a backup of Parquet. Save your edited analysis under
a new filename before regenerating the exporter-owned notebook.

See README.md here for the path from videos to keypoints to reconstructed landmarks,
coordinate conventions, confidence, and the difference between raw and filtered.
"""), cell('code', setup + LOAD),
        cell('markdown', """## Select a data channel

Each channel belongs to a source/model and reference frame. Body/hand/face prefixes
identify points within a tracker; they are not different people. Select the channel
index below. The DataFrame uses recorded frame IDs as rows and (name, component)
as column pairs. The array uses (frames, names, components). NaN means unavailable.
2D: XY/confidence; 3D points: XYZ; segment poses: XYZ and world WXYZ quaternions.
Position units are read from metadata; confidence/quaternions are dimensionless.
"""), cell('code', TABLE),
        cell('markdown', """## Plot a coordinate over time

Use recorded seconds rather than assuming a frame rate. NaNs appear as gaps.
A quaternion component is not an angle; confidence is not a distance or spatial
error. Start by inspecting a coordinate before attempting derivatives or joint
angles. This is a plot of one channel, not a reconstructed skeleton animation.
"""), cell('code', PLOT)]
    document = dict(nbformat=4, nbformat_minor=5, metadata=dict(
        kernelspec=dict(display_name='Python 3', language='python', name='python3'),
        language_info=dict(name='python')), cells=cells)
    for index, entry in enumerate(cells):
        entry['id'] = f'freemocap-{index}'
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
