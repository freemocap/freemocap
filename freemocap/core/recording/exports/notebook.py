"""Generate a portable recording notebook following the v1.8.2 walkthrough.

Imports, editable variables, trajectories, and animated points follow the original
FreeMoCap template [@freemocapNotebookV182]. Loading uses V2 channel metadata.
"""
import json
from pathlib import Path

IMPORTS = """from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
from plotly.subplots import make_subplots
import plotly.graph_objects as go
"""

LOAD = r"""# The export snapshot lives in this notebook's metadata.
notebook = json.loads(notebook_path.read_text(encoding='utf-8'))
snapshot = notebook['metadata']['freemocap']
RUN_ID = snapshot['run_id']
CHANNELS = list(snapshot['channels'].values())
parquet_path = path_to_recording / snapshot['source_file']
with parquet_path.open('rb') as stream:
    actual_hash = hashlib.file_digest(stream, 'sha256').hexdigest()
if actual_hash != snapshot['source_sha256']:
    raise ValueError('The recording changed after this notebook was exported. Export a new explorer for the new result.')
print('Selected run:', RUN_ID)
for index, channel in enumerate(CHANNELS):
    context = channel['context']
    print(index, context['channel'], context['source'], context['reference_frame'])
"""

TABLE = r"""def read_channel(kind):
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

JOINT = """# Choose any name printed above, then rerun the plotting cells.
joint_to_plot = next((name for name in channel['names'] if name in ('nose', 'body.nose')),
                     channel['names'][0])
joint_to_plot_index = channel['names'].index(joint_to_plot)
joint_data = values[:, joint_to_plot_index, :]
elapsed_time = times.to_numpy() - times.iloc[0]
"""

PLOT = r"""# One plot per coordinate, with shared time axes for zooming.
coordinates = [axis for axis in ('x', 'y', 'z') if axis in channel['components']]
fig = make_subplots(rows=len(coordinates), cols=1, shared_xaxes=True,
                    subplot_titles=[f'{joint_to_plot}: {axis.upper()}' for axis in coordinates])
for row, axis in enumerate(coordinates, start=1):
    component_index = channel['components'].index(axis)
    unit = channel['units'][component_index]
    fig.add_trace(go.Scatter(x=elapsed_time, y=joint_data[:, component_index],
                            mode='lines', name=axis.upper(), connectgaps=False), row=row, col=1)
    fig.update_yaxes(title_text=f'{axis.upper()} ({unit})', row=row, col=1)
fig.update_xaxes(title_text='Elapsed time (s)', row=len(coordinates), col=1)
fig.update_layout(height=650, showlegend=False, title=f"{context['source']}: {joint_to_plot}")
fig.show()
"""

ANIMATION = r"""# Increase frame_step for a lighter preview of a long recording.
frame_step = 1
if not all(axis in channel['components'] for axis in ('x', 'y', 'z')):
    print('Select a 3D channel above to view the movement in 3D.')
else:
    xyz_indices = [channel['components'].index(axis) for axis in ('x', 'y', 'z')]
    xyz = values[:, :, xyz_indices]
    frame_indices = list(range(0, len(xyz), frame_step))

    def points_at(index):
        return go.Scatter3d(x=xyz[index, :, 0], y=xyz[index, :, 1], z=xyz[index, :, 2],
                            mode='markers', marker=dict(size=3), text=channel['names'],
                            hovertemplate='%{text}<br>X: %{x}<br>Y: %{y}<br>Z: %{z}<extra></extra>')

    # One fixed 3-meter cube, centered on the median across all frames and points.
    # Outliers outside the cube stay outside the view; they never expand the axes.
    scene = dict(aspectmode='cube')
    for coordinate, axis in enumerate(('x', 'y', 'z')):
        finite = xyz[:, :, coordinate][np.isfinite(xyz[:, :, coordinate])]
        center = float(np.median(finite)) if finite.size else 0.0
        unit = channel['units'][xyz_indices[coordinate]]
        # Pixel-space recordings have no metric scale: use a fixed 3000-pixel cube.
        half_width = {'mm': 1500.0, 'cm': 150.0, 'm': 1.5, 'px': 1500.0}[unit]
        scene[axis + 'axis'] = dict(title=f'{axis.upper()} ({unit})',
                                    range=[center - half_width, center + half_width],
                                    autorange=False)

    frames = [go.Frame(data=[points_at(i)], name=str(table.index[i])) for i in frame_indices]
    # Playback uses the median recorded interval; slider labels retain exact timestamps.
    intervals = np.diff(times.to_numpy()[frame_indices])
    positive_intervals = intervals[np.isfinite(intervals) & (intervals > 0)]
    duration_ms = float(np.median(positive_intervals) * 1000) if positive_intervals.size else 33.0
    animation = go.Figure(data=[points_at(0)], frames=frames)
    animation.update_layout(
        height=700, scene=scene, title=f"{context['channel']}: {context['source']}",
        updatemenus=[dict(type='buttons', showactive=False, buttons=[
            dict(label='Play', method='animate', args=[None, dict(
                frame=dict(duration=duration_ms, redraw=True), transition=dict(duration=0), fromcurrent=True)]),
            dict(label='Pause', method='animate', args=[[None], dict(
                frame=dict(duration=0, redraw=False), mode='immediate')])])],
        sliders=[dict(currentvalue=dict(prefix='Frame / elapsed seconds: '), steps=[
            dict(label=f'{table.index[i]} / {elapsed_time[i]:.3f}', method='animate',
                 args=[[str(table.index[i])], dict(mode='immediate',
                       frame=dict(duration=0, redraw=True), transition=dict(duration=0))])
            for i in frame_indices])])
    animation.show()
"""


def write_notebook(path: Path, *, snapshot: dict) -> None:
    def cell(kind, source):
        result = dict(cell_type=kind, metadata={}, source=source.splitlines(keepends=True))
        if kind == 'code':
            result.update(execution_count=None, outputs=[])
        return result

    recording_path = '.'
    cells = [
        cell('markdown', """## Load necessary libraries

We'll use NumPy and Pandas to load your recording, and Plotly for interactive plots.
Your notebook environment needs numpy, pandas, pyarrow, and plotly.
"""),
        cell('code', IMPORTS),
        cell('markdown', """## Define variables

Run from this notebook's folder, or edit the paths below to match its location.
"""),
        cell('code', f'path_to_recording = Path({recording_path!r})\nnotebook_path = Path({path.name!r})\n'),
        cell('markdown', """## Load your recording

The list below shows the saved data available in this export.
"""),
        cell('code', LOAD),
        cell('code', r"""# Pick a channel index from the list above.
channel_index = 0
channel = CHANNELS[channel_index]
context = channel['context']
print('Available names:')
print(*channel['names'], sep='\n')
"""),
        cell('markdown', """### Load the selected channel

The array is ordered as frames, names, components. Missing samples stay as NaN.
"""),
        cell('code', TABLE),
        cell('markdown', """## Choose a joint

Change `joint_to_plot` to a name from the list above to explore another point.
For segment poses, these points are segment origins.
"""),
        cell('code', JOINT),
        cell('markdown', """## Plotting

Here are your chosen point's coordinates over time. Drag to zoom; hover to inspect.
Units come from the recording. Gaps are missing samples.
"""),
        cell('code', PLOT),
        cell('markdown', """## 3D Plotting

Press **Play** to watch the recorded points move. Drag to rotate the view, or use
the slider to choose a frame. The view stays fixed at three meters per side,
centered on the median position. A 2D channel only has the coordinate plots above.
"""),
        cell('code', ANIMATION),
    ]
    document = dict(nbformat=4, nbformat_minor=5, metadata=dict(
        kernelspec=dict(display_name='Python 3', language='python', name='python3'),
        language_info=dict(name='python'), freemocap=snapshot), cells=cells)
    for index, entry in enumerate(cells):
        entry['id'] = f'freemocap-{index}'
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
