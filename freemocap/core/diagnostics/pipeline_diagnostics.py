"""Self-describing diagnostic payloads shared by live delivery and recorded reports."""

from dataclasses import dataclass
from typing import Literal

import numpy as np
from skellyforge.core.skeleton.pose.rigid_body_diagnostics import RigidBodyResidual

from freemocap.core.skeletons.skeleton_reconstruction import SkeletonReconstruction
from freemocap.core.tasks.triangulation.helpers.reprojection_diagnostics import NamedReprojectionDiagnostics


@dataclass(frozen=True, slots=True)
class ReprojectionFrame:
    source_ids: tuple[str, ...]
    point_names: tuple[str, ...]
    units: str
    columns: tuple[str, ...]
    dtype: str
    data: bytes


@dataclass(frozen=True, slots=True)
class PipelineDiagnostics:
    length_units: Literal['millimeters', 'pixels']
    reprojection: tuple[ReprojectionFrame, ...]
    rigid_body: dict[str, dict[str, RigidBodyResidual]]


def frame_diagnostics(
    *, reprojection: tuple[NamedReprojectionDiagnostics, ...],
    reconstructions: dict[str, SkeletonReconstruction], length_units: Literal['millimeters', 'pixels'],
) -> PipelineDiagnostics:
    blocks: list[ReprojectionFrame] = []
    for block in reprojection:
        values = block.values
        if values.errors.ndim != 2:
            raise ValueError('Live diagnostics require one frame per block')
        packed = np.stack((values.errors, values.observed, values.reconstructed, values.weights), axis=-1).astype('<f4')
        blocks.append(ReprojectionFrame(
            source_ids=block.source_ids, point_names=block.point_names, units=values.units,
            columns=('error', 'observed', 'reconstructed', 'weight'), dtype='float32_le', data=packed.tobytes(),
        ))
    return PipelineDiagnostics(
        length_units=length_units, reprojection=tuple(blocks),
        rigid_body={model_id: frame.rigid_body_residuals for model_id, frame in reconstructions.items()},
    )
