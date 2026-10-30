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
import polars as pl
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

TABLE = r"""# Select the complete channel identity before collecting numeric columns.
# Lazy scans push selection/projection into the Parquet reader [@polarsParquetScan].
storage_kinds = (['SEGMENT_ORIGINS', 'ROTATIONS_WORLD']
                 if context['channel'] == 'SEGMENT_POSES' else [context['channel']])
reference = context['reference_frame']
reference_filter = (pl.col('reference_frame').is_null() if reference is None
                    else pl.col('reference_frame') == reference)
channel_query = (pl.scan_parquet(parquet_path)
    .filter((pl.col('run_id') == RUN_ID) & (pl.col('sensor_group') == context['sensor_group'])
            & (pl.col('source') == context['source']) & pl.col('channel').is_in(storage_kinds)
            & reference_filter)
    .select('channel', 'frame_number', 'timestamp_s', 'name', 'component', 'units', 'value'))
if context['channel'] == 'SEGMENT_POSES':
    channel_query = channel_query.with_columns(
        pl.when(pl.col('channel') == 'ROTATIONS_WORLD')
        .then(pl.concat_str([pl.lit('q'), pl.col('component')]))
        .otherwise(pl.col('component')).alias('component'))
elif context['channel'] == 'OVERLAY_2D':
    channel_query = channel_query.with_columns(pl.col('component').replace({'visibility': 'confidence'}))
rows = channel_query.collect(engine='streaming')
if rows.is_empty():
    raise ValueError('No saved samples for this channel')
if any(rows[name].null_count() for name in ('frame_number', 'timestamp_s', 'name', 'component', 'units')):
    raise ValueError('Missing sample identity, timestamp or units')
if not rows['timestamp_s'].is_finite().all() or (rows['frame_number'] < 0).any():
    raise ValueError('Invalid sample identity or timestamp')
clock = rows.group_by('frame_number').agg(
    pl.col('timestamp_s').first().alias('first'),
    pl.col('timestamp_s').min().alias('min'),
    pl.col('timestamp_s').max().alias('max')).sort('frame_number')
# Each selected display channel must have one exact timestamp per frame.
if (clock['max'] != clock['min']).any():
    raise ValueError('Conflicting timestamps in the selected channel')
times = clock['first']
frame_numbers = clock['frame_number'].to_numpy()
if np.any(np.diff(times.to_numpy()) <= 0):
    raise ValueError('Channel timestamps must increase with frame numbers')
if rows.select(pl.struct('frame_number', 'name', 'component').is_duplicated().any()).item():
    raise ValueError('Duplicate sample in the selected channel')
# These dictionaries describe axes once; numerical data stays in arrays.
name_positions = {name: index for index, name in enumerate(channel['names'])}
component_positions = {name: index for index, name in enumerate(channel['components'])}
indexed_rows = rows.with_columns(
    pl.col('name').replace_strict(name_positions, return_dtype=pl.Int64).alias('name_index'),
    pl.col('component').replace_strict(component_positions, return_dtype=pl.Int64).alias('component_index'))
expected_units = rows['component'].replace_strict(dict(zip(channel['components'], channel['units'])))
if (rows['units'] != expected_units).any():
    raise ValueError('Sample units differ from the declared components')
tensor_shape = (len(frame_numbers), len(channel['names']), len(channel['components']))
flat_indices = np.ravel_multi_index((
    np.searchsorted(frame_numbers, rows['frame_number'].to_numpy()),
    indexed_rows['name_index'].to_numpy(), indexed_rows['component_index'].to_numpy()), tensor_shape)
values = np.full(tensor_shape, np.nan, dtype=np.float64)
present = np.zeros(tensor_shape, dtype=bool)
values.reshape(-1)[flat_indices] = rows['value'].to_numpy()
present.reshape(-1)[flat_indices] = True
table = rows.select('frame_number', 'name', 'component', 'value')
print('Array axes: frames, names, components; shape:', values.shape)
print('Components:', dict(zip(channel['components'], channel['units'])))
table.head()
"""

JOINT = """# Choose any name printed above, then rerun the plotting cells.
joint_to_plot = next((name for name in channel['names'] if name in ('nose', 'body.nose')),
                     channel['names'][0])
joint_to_plot_index = channel['names'].index(joint_to_plot)
joint_data = values[:, joint_to_plot_index, :]
elapsed_time = times.to_numpy() - times[0]
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

    frames = [go.Frame(data=[points_at(i)], name=str(frame_numbers[i])) for i in frame_indices]
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
            dict(label=f'{frame_numbers[i]} / {elapsed_time[i]:.3f}', method='animate',
                 args=[[str(frame_numbers[i])], dict(mode='immediate',
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

We'll use Polars to select saved columns, NumPy for data tensors, and Plotly for interactive plots.
Your notebook environment needs numpy, polars>=2,<3, and plotly>=6,<7.
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
