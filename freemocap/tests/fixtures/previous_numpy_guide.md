# Reading NumPy arrays

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
