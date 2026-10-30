"""Re-encode all accepted reference box and timing channels through dense publication."""
import json
import os
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pyarrow as pa
import pytest
from skellytracker.core.data_primitives.observation import Observation, StageObservation
from skellytracker.core.data_primitives.bounding_box import BoundingBox

from freemocap.core.recording.parquet_storage.recording_view import recording_view
from freemocap.core.recording.parquet_storage.selected_batches import ChannelQuery, selected_batches
from freemocap.core.recording.result_processing.saved_reconstruction import read_saved_channel
from freemocap.core.recording.sample_encoding.channel_series import SeriesSampling
from freemocap.core.recording.sample_encoding.observation_samples import box_series_batches, timing_series_batches
from freemocap.core.tracking.observation_series import RecordingObservationSeries
from freemocap.system.recording_structure.recording_structure import RecordingStructure
from freemocap.tests.reference_paths import prepared_root
from freemocap.tools.datasets.catalog import TEST_DATA
from freemocap.tools.datasets.preparation import file_digest


def reference_publication_inputs():
    root = prepared_root() / TEST_DATA.name
    recording = Path(json.loads((root / 'ready.json').read_text(encoding='utf-8'))['recording'])
    assert recording.resolve().is_relative_to((root / 'current').resolve())
    structure = RecordingStructure(base_directory=recording.parent, recording_name=recording.name)
    original_digest = file_digest(structure.data_parquet_path)
    inputs = []
    with recording_view(structure.data_parquet_path) as view:
        run_id = view.metadata.selected_run_id
        for channel in view.metadata.runs[run_id].channels:
            if channel.kind not in ('BOXES_2D', 'TIMESTAMPS'):
                continue
            saved = read_saved_channel(structure=structure, run_id=run_id, metadata=view.metadata, channel=channel, view=view)
            assert len(saved.frames) == 222
            sampling = SeriesSampling(frame_numbers=saved.frames, timestamps_s=saved.timestamps_s, run_id=run_id, batch_size=79)
            expected = pa.Table.from_batches(list(selected_batches(view, (ChannelQuery(run_id, channel.sensor_group,
                channel.source, str(channel.kind), channel.reference_frame),)))).replace_schema_metadata(None)
            series = None
            originals = []
            if channel.kind == 'BOXES_2D':
                series = RecordingObservationSeries(camera_id=channel.reference_frame, image_size=(1, 1),
                    frame_numbers=saved.frames, timestamps_s=saved.timestamps_s)
                components = tuple(channel.components)
                order = [components.index(name) for name in ('x1', 'y1', 'x2', 'y2', 'confidence')]
                for index, frame_number in enumerate(saved.frames):
                    stages = {}
                    for point, name in enumerate(channel.names):
                        values = saved.values[index, point]
                        present = not np.isnan(values).all()
                        stages[name] = StageObservation(name=name,
                            bounding_boxes=[BoundingBox(*values[order])] if present else [],
                            detector_ran=bool(values[components.index('detector_ran')]) if present else False)
                    observation = Observation(frame_number=frame_number, image_size=(1, 1), stages=stages)
                    originals.append(observation)
                    series.store(index, observation)
                series.finalize()
            inputs.append((channel, series, sampling, expected, originals))
    return structure, original_digest, inputs


@pytest.mark.skipif(not os.environ.get('FREEMOCAP_PROVENANCE_PREPARED_ROOT'), reason='Set prepared reference-data root')
def test_reference_boxes_and_timestamps_are_exact_through_dense_column_publication():
    structure, original_digest, inputs = reference_publication_inputs()
    boxes = clocks = 0
    with patch.object(BoundingBox, '__init__', side_effect=AssertionError('No reconstruction during publication')):
        for channel, series, sampling, expected, _ in inputs:
            if series is None:
                batches = list(timing_series_batches(sampling=sampling, channel=channel))
                clocks += 1
            else:
                batches = list(box_series_batches(series=series, sampling=sampling, channel=channel))
                boxes += 1
            actual = pa.Table.from_batches(batches)
            assert actual.equals(expected)
    assert boxes == 3 and clocks == 4
    assert file_digest(structure.data_parquet_path) == original_digest
