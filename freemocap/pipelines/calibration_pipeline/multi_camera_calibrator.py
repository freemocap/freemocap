import logging

from pydantic import BaseModel
from skellycam import CameraId

from freemocap.pipelines.calibration_pipeline.calibration_camera_node_output_data import CalibrationCameraNodeOutputData
from freemocap.pipelines.calibration_pipeline.multi_camera_calibration.least_squares_optimizer import \
    SparseBundleAdjustmentOptimizer, SparseBundleAdjustmentOptimizerInputData
from freemocap.pipelines.calibration_pipeline.shared_view_accumulator import SharedViewAccumulator

logger = logging.getLogger(__name__)

from freemocap.pipelines.calibration_pipeline.single_camera_calibrator import SingleCameraCalibrator


class MultiCameraCalibrationEstimate(BaseModel):
    pass


class MultiCameraCalibrator(BaseModel):
    principal_camera_id: CameraId
    camera_id_to_index: dict[CameraId, int]
    shared_view_accumulator: SharedViewAccumulator

    single_camera_calibrators: dict[CameraId, SingleCameraCalibrator] | None = None
    multi_camera_calibration_estimate: MultiCameraCalibrationEstimate | None = None
    minimum_views_to_reconstruct: int | None = 20

    @property
    def has_calibration(self) -> bool:
        if self.single_camera_calibrators is None or self.multi_camera_calibration_estimate is None:
            return False
        return all(single_camera_calibrator.has_calibration for single_camera_calibrator in
                   self.single_camera_calibrators.values()) and self.multi_camera_calibration_estimate.has_calibration

    @classmethod
    def from_camera_ids(cls, camera_ids: list[CameraId], principal_camera_id: CameraId | None = None):
        return cls(principal_camera_id=principal_camera_id if principal_camera_id is not None else min(camera_ids),
                   camera_id_to_index={camera_id: index for index, camera_id in enumerate(camera_ids)},
                   shared_view_accumulator=SharedViewAccumulator.create(camera_ids=camera_ids),
                   )

    def receive_camera_node_output(self, multi_frame_number: int,
                                   camera_node_output_by_camera: dict[CameraId, CalibrationCameraNodeOutputData]):

        self.add_observations_to_single_camera_calibrators(camera_node_output_by_camera)

        self.shared_view_accumulator.receive_camera_node_output(multi_frame_number=multi_frame_number,
                                                                camera_node_output_by_camera=camera_node_output_by_camera)

        logger.trace(f"Shared view accumulator: {self.shared_view_accumulator.shared_view_count_by_camera}")

    def add_observations_to_single_camera_calibrators(self, camera_node_output_by_camera: dict[CameraId, CalibrationCameraNodeOutputData]):
        if self.single_camera_calibrators is None:
            self.initialize_single_camera_calibrators(camera_node_output_by_camera)
        for camera_id, output in camera_node_output_by_camera.items():
            self.single_camera_calibrators[camera_id].add_observation(observation=output.charuco_observation)

    def initialize_single_camera_calibrators(self, camera_node_output_by_camera: dict[CameraId, CalibrationCameraNodeOutputData]):

        self.single_camera_calibrators:dict[CameraId, SingleCameraCalibrator] = {}
        for camera_id, node_output in camera_node_output_by_camera.items():
            self.single_camera_calibrators[camera_id] = SingleCameraCalibrator.create_initial(
                camera_id=camera_id,
                image_size=node_output.charuco_observation.image_size,
                all_aruco_marker_ids=node_output.charuco_observation.all_aruco_ids,
                all_aruco_corners_in_object_coordinates=node_output.charuco_observation.all_aruco_corners_in_object_coordinates,
                all_charuco_corner_ids=node_output.charuco_observation.all_charuco_ids,
                all_charuco_corners_in_object_coordinates=node_output.charuco_observation.all_charuco_corners_in_object_coordinates
            )

    def all_cameras_have_min_shared_views(self, min_shared_views: int | None = None) -> bool:
        return self.shared_view_accumulator.all_cameras_have_min_shared_views(
            min_shared_views=self.minimum_views_to_reconstruct if min_shared_views is None else min_shared_views)


    def calibrate(self) -> MultiCameraCalibrationEstimate:
        logger.debug(
            f"Calibrating multi-camera system for cameras: {self.single_camera_calibrators.keys()} with principal camera: {self.principal_camera_id} and {len(self.shared_view_accumulator.shared_target_views)} shared views")

        [calibrator.update_calibration_estimate() for calibrator in self.single_camera_calibrators.values()]

        self.run_multi_camera_optimization()
        logger.success(
            f"Multi-camera calibration complete! \n {self.multi_camera_calibration_estimate.model_dump_json(indent=2)}")
        return self.multi_camera_calibration_estimate

    def run_multi_camera_optimization(self):
        input_data = SparseBundleAdjustmentOptimizerInputData.create(camera_matricies={camera_id:calibrator.camera_matrix for camera_id, calibrator in self.single_camera_calibrators.items()},
                                                                     input_2d_observations_in_image_coordinates_by_camera=self.shared_view_accumulator.to_image_points_by_camera(),
                                                                     )

        mc_calibrator = SparseBundleAdjustmentOptimizer.create(input_data=input_data)
        self.multi_camera_calibration_estimate = mc_calibrator.run_iterative_bundle_adjustment()
        return self.multi_camera_calibration_estimate
