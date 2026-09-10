"""Generate a backend-encoded diagnostic frame for the browser contract test."""

from pathlib import Path

import numpy as np
from skellyforge.core.skeleton.pose.rigid_body_diagnostics import RigidBodyResidual

from freemocap.core.diagnostics.pipeline_diagnostics import frame_diagnostics
from freemocap.core.skeletons.skeleton_reconstruction import SkeletonReconstruction
from freemocap.core.streaming.message_model import FrameMessage, encode_message
from freemocap.core.tasks.triangulation.helpers.reprojection_diagnostics import NamedReprojectionDiagnostics, ReprojectionDiagnostics


def main() -> None:
    diagnostics = frame_diagnostics(
        reprojection=(NamedReprojectionDiagnostics(source_ids=('camera-a', 'camera-b'), point_names=('body.nose',),
            values=ReprojectionDiagnostics(errors=np.array([[2.], [np.nan]]), observed=np.array([[True], [False]]),
                reconstructed=np.array([[True], [True]]), weights=np.array([[1.], [np.nan]]), units='pixels')),),
        reconstructions={'human': SkeletonReconstruction(model_id='human', rigid_body_residuals={
            'arm': RigidBodyResidual(measured_length=305., reference_length=300., residual=5., reference_kind='prior_live_fit'),
            'leg': RigidBodyResidual(measured_length=None, reference_length=400., residual=None, reference_kind='prior_live_fit'),
        })}, length_units='millimeters',
    )
    destination = Path(__file__).resolve().parents[3] / 'freemocap-ui/e2e/fixtures/diagnostics.bin'
    destination.write_bytes(encode_message(FrameMessage(frame_number=42, diagnostics=diagnostics)))


if __name__ == '__main__':
    main()
