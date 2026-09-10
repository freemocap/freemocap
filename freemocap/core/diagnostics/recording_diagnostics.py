"""Persist full diagnostic arrays and summaries without changing reconstruction policy."""

from dataclasses import asdict
import json
from pathlib import Path
from typing import Literal

import numpy as np
from skellyforge.core.skeleton.pose.rigid_body_diagnostics import ResidualAccumulator

from freemocap.core.reconstruction.posthoc_reconstruction import RecordingTriangulation
from freemocap.core.reconstruction.recording_reconstruction import ModelRecordingReconstruction


def write_recording_diagnostics(
    *, path: Path, triangulation: RecordingTriangulation,
    reconstructions: dict[str, ModelRecordingReconstruction], frame_numbers: tuple[int, ...],
    length_units: Literal['millimeters', 'pixels'],
) -> None:
    """One NPZ archive: named axes and JSON metadata plus non-object numeric arrays."""
    if len(frame_numbers) != triangulation.reconstruction.points_3d.shape[0]:
        raise ValueError('Diagnostic frame numbers must cover the triangulation')
    arrays: dict[str, np.ndarray] = {'frame_numbers': np.asarray(frame_numbers, dtype=np.int64)}
    metadata: dict[str, object] = {
        'version': 1, 'length_units': length_units, 'source_ids': triangulation.sources,
        'point_names': triangulation.diagnostic_point_names, 'reprojection': None,
    }
    reprojection = triangulation.reconstruction.diagnostics
    if reprojection is not None:
        arrays.update(reprojection_error=reprojection.errors, observation_present=reprojection.observed,
                      reconstruction_valid=reprojection.reconstructed, solver_weights=reprojection.weights)
        metadata['reprojection'] = {'units': reprojection.units, 'axes': ['source', 'frame', 'point'],
                                    'summaries': [asdict(summary) for summary in reprojection.summaries()]}
    model_metadata: dict[str, object] = {}
    for model_index, (model_id, reconstruction) in enumerate(reconstructions.items()):
        if len(reconstruction.frames) != len(frame_numbers):
            raise ValueError('Rigid-body diagnostics must cover the recording frame grid')
        names = tuple(dict.fromkeys(name for frame in reconstruction.frames if frame is not None for name in frame.rigid_body_residuals))
        values = np.full((len(frame_numbers), len(names), 3), np.nan, dtype=np.float64)
        accumulators = {name: ResidualAccumulator() for name in names}
        references: set[str] = set()
        for frame_index, frame in enumerate(reconstruction.frames):
            for segment_index, name in enumerate(names):
                reading = frame.rigid_body_residuals.get(name) if frame is not None else None
                accumulators[name].add(residual=reading.residual if reading else None)
                if reading is not None:
                    references.add(reading.reference_kind)
                    values[frame_index, segment_index] = [
                        value if value is not None else np.nan
                        for value in (reading.measured_length, reading.reference_length, reading.residual)
                    ]
        key = f'rigid_body_{model_index}'
        arrays[key] = values
        model_metadata[model_id] = {'array': key, 'segment_names': names,
                                   'columns': ['measured_length', 'reference_length', 'residual'],
                                   'reference_kinds': sorted(references),
                                   'summaries': {name: asdict(accumulator.summary()) for name, accumulator in accumulators.items()}}
    metadata['rigid_body'] = model_metadata
    arrays['metadata'] = np.asarray(json.dumps(metadata, allow_nan=False))
    with path.open('wb') as output:
        np.savez_compressed(output, **arrays)
