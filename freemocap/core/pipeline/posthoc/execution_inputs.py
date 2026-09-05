"""External geometry requirements of the operations selected for execution."""

from dataclasses import dataclass

from freemocap.core.pipeline.posthoc.processing_request import ProcessingStage
from freemocap.core.recording.resolved_camera_geometry import ResolvedCameraGeometry


@dataclass(frozen=True, slots=True)
class CameraExecutionInputs:
    camera_ids: tuple[str, ...]
    geometry: tuple[ResolvedCameraGeometry, ...]

    def validate_for(self, stages: tuple[ProcessingStage, ...]) -> None:
        if len(set(self.camera_ids)) != len(self.camera_ids):
            raise ValueError("Camera inputs contain duplicate camera IDs")
        if ProcessingStage.TRIANGULATION in stages and not self.camera_ids:
            raise ValueError("Point reconstruction requires input cameras")
        requires_geometry = ProcessingStage.REPROJECTION in stages or (
            ProcessingStage.TRIANGULATION in stages and len(self.camera_ids) > 1
        )
        if not requires_geometry:
            return
        if not self.camera_ids:
            raise ValueError("Reprojection requires target cameras")
        resolved_ids = tuple(camera.camera_id for camera in self.geometry)
        if len(set(resolved_ids)) != len(resolved_ids):
            raise ValueError("Camera geometry contains duplicate camera IDs")
        if not set(self.camera_ids).issubset(resolved_ids):
            raise ValueError(
                "Selected triangulation/reprojection requires resolved camera geometry"
            )
