"""Independent display projection used to compare native exports with CSV/notebooks."""
from types import SimpleNamespace

import numpy as np


def display_projection(dataset, context):
    if context['channel'] == 'SEGMENT_POSES':
        origin = display_projection(dataset, dict(context, channel='SEGMENT_ORIGINS'))
        rotation = display_projection(dataset, dict(context, channel='ROTATIONS_WORLD'))
        np.testing.assert_array_equal(origin.frames, rotation.frames)
        np.testing.assert_array_equal(origin.timestamps, rotation.timestamps)
        assert origin.names == rotation.names
        return SimpleNamespace(values=np.concatenate((origin.values, rotation.values), axis=-1),
            present=np.concatenate((origin.present, rotation.present), axis=-1), frames=origin.frames,
            timestamps=origin.timestamps, names=origin.names,
            components=(*origin.components, *(f'q{component}' for component in rotation.components)),
            units=(*origin.units, *rotation.units))
    static = context.get('static', False)
    candidates = dataset.static_tensors if static else dataset.time_series
    matches = []
    for data in candidates:
        tensor = data if static else data.data_tensor
        layout = tensor.tensor_layout
        source = layout.source_identity
        if (source.sensor_group, source.source_id, layout.reference_id, layout.channel_kind) == (
                context['sensor_group'], context['source'], context['reference_frame'], context['channel']):
            matches.append(data)
    assert len(matches) == 1
    data = matches[0]
    tensor = data if static else data.data_tensor
    layout = tensor.tensor_layout
    names = layout.axes[layout.axis_index('entity_identity')].identifiers
    authored = layout.axes[layout.axis_index('component_identity')].identifiers
    canonical = (('x', 'y', 'z') if set(authored) == {'x', 'y', 'z'} else
                 ('w', 'x', 'y', 'z') if set(authored) == {'w', 'x', 'y', 'z'} else authored)
    order = [authored.index(name) for name in canonical]
    axes = (['entity_identity', 'component_identity'] if static else
            [data.sample_axis_name, 'entity_identity', 'component_identity'])
    source_axes = [layout.axis_index(name) for name in axes]
    values = np.moveaxis(tensor.data_values, source_axes, range(len(axes)))
    presence = np.moveaxis(tensor.companion_values('entry_presence'), source_axes, range(len(axes)))
    return SimpleNamespace(values=np.take(values, order, axis=-1), present=np.take(presence, order, axis=-1),
        frames=np.empty(0, dtype=np.int64) if static else data.sample_timing.sample_ids,
        timestamps=np.empty(0) if static else data.sample_timing.timestamps_s,
        names=names, components=tuple('confidence' if context['channel'] == 'OVERLAY_2D' and name == 'visibility' else name
                                      for name in canonical), units=tuple(layout.component_units[index] for index in order))
