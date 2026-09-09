"""Recording alignment integrating camera geometry, tracker mapping, and Forge."""

from dataclasses import dataclass, replace

import numpy as np
from numpy.typing import NDArray
from freemocap.core.reconstruction.alignment_config import MocapAlignmentConfig
from skellyforge.core.biomechanics.alignment_definition import AlignmentDefinition
from skellyforge.core.biomechanics.reference_alignment import (
    ReferenceAlignmentOutcome, ReferenceAlignmentRequest, ReferenceAlignmentResult, estimate_reference_alignment,
)
from skellyforge.core.math.geometry.spatial_vectors import Point
from skellyforge.core.math.geometry.transform_math import Transform

from freemocap.core.reconstruction.alignment_evidence import AlignmentEvidence, AlignmentEvidenceRequest
from freemocap.core.reconstruction.coordinate_conventions import RECONSTRUCTION_TO_CALIBRATION
from freemocap.core.reconstruction.posthoc_reconstruction import RecordingTriangulation
from freemocap.core.skeletons.tracked_skeleton_bundle import TrackedSkeletonBundle
from freemocap.core.tasks.calibration.shared.camera_model import CameraModel


@dataclass(frozen=True, slots=True, kw_only=True)
class MocapAlignmentRequest:
    triangulation: RecordingTriangulation
    camera_geometry: dict[str, CameraModel]
    bundle: TrackedSkeletonBundle
    definition: AlignmentDefinition
    timestamps_seconds: NDArray[np.float64]
    has_explicit_ground: bool
    config: MocapAlignmentConfig


@dataclass(frozen=True, slots=True, kw_only=True)
class AlignedMocapRecording:
    triangulation: RecordingTriangulation
    camera_geometry: dict[str, CameraModel]
    alignment: ReferenceAlignmentResult


def align_mocap_recording(*, request: MocapAlignmentRequest) -> AlignedMocapRecording:
    body_tracks = ()
    foot_contacts = ()
    if request.config.enabled and not request.has_explicit_ground and len(request.triangulation.sources) > 1:
        # Pixel reprojection errors come from the pixel-input recording triangulator.
        # Missing observations have NaN errors. This is geometric support, not detector probability.
        errors = request.triangulation.reconstruction.reprojection_error
        points = request.triangulation.reconstruction.points_3d
        calibration_points = RECONSTRUCTION_TO_CALIBRATION.convert_point(
            point=Point.from_prevalidated_array(array=points)
        ).array
        scores = np.zeros_like(errors)
        for index, source in enumerate(request.triangulation.sources):
            camera = request.camera_geometry[source]
            depth = calibration_points @ camera.extrinsics.rotation_matrix[2] + camera.extrinsics.translation[2]
            valid = np.isfinite(errors[index]) & (depth > 0)
            scores[index, valid] = 1 / (1 + (errors[index, valid] / request.config.reprojection_scale_px) ** 2)
        quality = np.sort(scores, axis=0)[-2]
        quality[~np.isfinite(points).all(axis=-1)] = 0.0
        evidence = AlignmentEvidence.collect(request=AlignmentEvidenceRequest(
            bundle=request.bundle, definition=request.definition,
            timestamps_seconds=request.timestamps_seconds, keypoint_names=request.triangulation.keypoint_names,
            positions=points, quality=quality, minimum_quality=request.config.body.minimum_quality,
        ))
        body_tracks, foot_contacts = evidence.body_tracks, evidence.foot_contacts
    alignment = estimate_reference_alignment(request=ReferenceAlignmentRequest(
        enabled=request.config.enabled, has_explicit_ground=request.has_explicit_ground,
        body_tracks=body_tracks, foot_contacts=foot_contacts, body_config=request.config.body, ground_config=request.config.ground,
    ))
    if alignment.outcome not in (ReferenceAlignmentOutcome.BODY_REFERENCE, ReferenceAlignmentOutcome.FOOT_SUPPORT):
        return AlignedMocapRecording(
            triangulation=request.triangulation, camera_geometry=request.camera_geometry, alignment=alignment,
        )
    transform = alignment.transform
    calibration_transform = Transform(
        rotation=RECONSTRUCTION_TO_CALIBRATION.convert_quaternion(quaternion=transform.rotation),
        translation=RECONSTRUCTION_TO_CALIBRATION.convert_displacement(displacement=transform.translation),
    )
    points = transform.apply(points=Point.from_prevalidated_array(array=request.triangulation.reconstruction.points_3d)).array
    return AlignedMocapRecording(
        triangulation=replace(request.triangulation, reconstruction=replace(request.triangulation.reconstruction, points_3d=points)),
        camera_geometry={source: camera.in_world_frame(transform=calibration_transform) for source, camera in request.camera_geometry.items()},
        alignment=alignment,
    )
