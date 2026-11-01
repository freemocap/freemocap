# Reading NumPy datasets

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
channel = next(item for item in manifest['channels']
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
if not len(times):
    raise ValueError('The selected channel has no samples')
plt.plot(times - times[0], trajectory_values)
plt.xlabel('Elapsed time (s)')
plt.ylabel(component_name + ' (' + layout['component_units'][components.index(component_name)] + ')')
plt.title(name)
plt.show()
```

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
