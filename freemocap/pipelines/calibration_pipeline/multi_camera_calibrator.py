from pydantic import BaseModel
from skellycam import CameraId

from freemocap.pipelines.calibration_pipeline.multi_camera_calibration.calibration_numpy_types import \
    PixelPoints2DByCamera, ObjectPoints3D, PointIds, RotationVectorsByCamera, TranslationVectorsByCamera
from freemocap.pipelines.calibration_pipeline.shared_view_accumulator import TargetViewByCamera
from freemocap.pipelines.calibration_pipeline.single_camera_calibrator import SingleCameraCalibrator
class MultiCameraCalibrationInputData(BaseModel):
    pixel_points2d: PixelPoints2DByCamera
    object_points3d: ObjectPoints3D
    points_ids: PointIds
    rotation_vectors: RotationVectorsByCamera
    translation_vectors: TranslationVectorsByCamera

import logging
logger = logging.getLogger(__name__)

class MultiCameraCalibrator(BaseModel):
    principal_camera_id: CameraId
    camera_id_to_index: dict[CameraId, int]
    single_camera_calibrators: dict[CameraId, SingleCameraCalibrator]

    @classmethod
    def initialize(cls,
                   shared_charuco_views: list[TargetViewByCamera],
                   calibrate_cameras: bool = True):

        # Calculate the calibration estimate for each camera

        charuco_view_by_camera = {}

        for target_view_by_camera in shared_charuco_views:
            for camera_id, camera_node_output in target_view_by_camera.views_by_camera.items():
                if camera_id not in charuco_view_by_camera:
                    charuco_view_by_camera[camera_id] = []
                charuco_view_by_camera[camera_id].append(camera_node_output)

        # Find the principal camera (usually Camera0, but this finds the lowest indexed camera)
        principal_camera_id = min(key for key in charuco_view_by_camera.keys())

        single_camera_calibrators = {}
        for camera_id, camera_node_outputs in charuco_view_by_camera.items():
            single_camera_calibrators[camera_id] = SingleCameraCalibrator.from_camera_node_outputs(
                camera_node_outputs=camera_node_outputs,
                calibrate_camera=calibrate_cameras)


        return cls(principal_camera_id=principal_camera_id,
                   single_camera_calibrators=single_camera_calibrators,
                     camera_id_to_index={camera_id: index for index, camera_id in enumerate(single_camera_calibrators.keys())}
                     )

    def calibrate(self):
        for single_camera_calibrator in self.single_camera_calibrators.values():
            single_camera_calibrator.update_calibration_estimate()
            logger.trace(f"Calibrated camera {single_camera_calibrator.camera_id}:\n{single_camera_calibrator.current_estimate.model_dump_json(indent=2)}")
        f=9