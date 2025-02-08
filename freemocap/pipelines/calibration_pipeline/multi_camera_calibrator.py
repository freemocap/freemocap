import logging

import numpy as np
from pydantic import BaseModel
from skellycam import CameraId

from freemocap.pipelines.calibration_pipeline.calibration_camera_node_output_data import CalibrationCameraNodeOutputData

from freemocap.pipelines.calibration_pipeline.shared_view_accumulator import SharedViewAccumulator, CameraPair

logger = logging.getLogger(__name__)

from freemocap.pipelines.calibration_pipeline.single_camera_calibrator import SingleCameraCalibrator, \
    TransformationMatrix


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

        if self.single_camera_calibrators is None:
            self.initialize_single_camera_calibrators(camera_node_output_by_camera)
        self.shared_view_accumulator.receive_camera_node_output(multi_frame_number=multi_frame_number,
                                                                camera_node_output_by_camera=camera_node_output_by_camera)

        logger.trace(f"Shared view accumulator: {self.shared_view_accumulator.get_shared_view_count_per_camera()}")

    def initialize_single_camera_calibrators(self, camera_node_output_by_camera: dict[
        CameraId, CalibrationCameraNodeOutputData]):

        self.single_camera_calibrators: dict[CameraId, SingleCameraCalibrator] = {}
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

    def calibrate(self):
        logger.debug(
            f"Calibrating multi-camera system for cameras: {self.single_camera_calibrators.keys()}"
            f" with principal camera: {self.principal_camera_id} and "
            f"{self.shared_view_accumulator.get_shared_view_count_per_camera()} shared views")

        for camera_pair, shared_views in self.shared_view_accumulator.target_views_by_camera_pair.items():
            logger.trace(f"Camera pair ({camera_pair}) has {len(shared_views)} shared views")
            for view in shared_views:
                camera_id = view.camera_pair.base_camera_id
                other_camera_id = view.camera_pair.other_camera_id
                self.single_camera_calibrators[camera_id].add_observation(observation=view.camera_node_output_by_camera[camera_id].charuco_observation)
                self.single_camera_calibrators[other_camera_id].add_observation(observation=view.camera_node_output_by_camera[other_camera_id].charuco_observation)



        [calibrator.update_calibration_estimate() for calibrator in self.single_camera_calibrators.values()]

        self.run_multi_camera_optimization()
        # logger.success(
        #     f"Multi-camera calibration complete! \n {self.multi_camera_calibration_estimate.model_dump_json(indent=2)}")
        # return self.multi_camera_calibration_estimate

    def run_multi_camera_optimization(self):
        # Step 1: Calculate secondary camera transforms for each camera pair
        camera_pair_secondary_camera_transform_estimates = {}
        for camera_pair in self.shared_view_accumulator.camera_pairs:
            base_camera_id = camera_pair.base_camera_id
            other_camera_id = camera_pair.other_camera_id

            charuco_transforms_in_base_camera_coordinates = self.single_camera_calibrators[
                base_camera_id].charuco_transformation_matrices
            charuco_transforms_in_other_camera_coordinates = self.single_camera_calibrators[
                other_camera_id].charuco_transformation_matrices

            other_camera_to_base_camera_transforms = []
            for base_camera_transform, other_camera_transform in zip(charuco_transforms_in_base_camera_coordinates,
                                                                     charuco_transforms_in_other_camera_coordinates):
                base_camera_to_board_transform = base_camera_transform.get_inverse()
                other_camera_to_base_camera_transforms.append(base_camera_to_board_transform @ other_camera_transform)

            mean_transform = TransformationMatrix.mean_from_transformation_matrices(
                other_camera_to_base_camera_transforms)
            camera_pair_secondary_camera_transform_estimates[camera_pair] = mean_transform

        logger.debug(
            f"Camera pair secondary camera transform estimates: {camera_pair_secondary_camera_transform_estimates}")

        # Step 2: Calculate each camera's transform relative to the principal camera
        transform_to_principal_camera_by_camera = {self.principal_camera_id: TransformationMatrix(matrix=np.eye(4),
                                                                                     reference_frame=f"camera {self.principal_camera_id}")}

        transform_to_principal_camera_by_camera.update({camera_id: None for camera_id in self.single_camera_calibrators.keys()
                                                        if camera_id != self.principal_camera_id})
        # Use the camera pairs to determine other camera transforms relative to the principal camera
        while any([transform is None for transform in transform_to_principal_camera_by_camera.values()]):
            logger.debug(f"Calculating camera transforms for cameras: {[camera_id for camera_id, transform in transform_to_principal_camera_by_camera.items() if transform is None]}")
            for camera_pair, transform in camera_pair_secondary_camera_transform_estimates.items():
                if transform_to_principal_camera_by_camera[camera_pair.other_camera_id] is not None:
                    continue
                if camera_pair.base_camera_id == self.principal_camera_id:
                    # Directly use the transform if base is principal camera
                    transform_to_principal_camera_by_camera[camera_pair.other_camera_id] = transform
                elif camera_pair.other_camera_id == self.principal_camera_id:
                    # Transform is inverse if other is principal camera
                    transform_to_principal_camera_by_camera[camera_pair.base_camera_id] = transform.get_inverse()
                else:
                    # If neither camera in the pair is the principal camera, we need to transform the other camera's transform
                    if camera_pair.base_camera_id in transform_to_principal_camera_by_camera:
                        base_to_principal = transform_to_principal_camera_by_camera[camera_pair.base_camera_id]
                        transform_to_principal_camera_by_camera[
                            camera_pair.other_camera_id] = base_to_principal @ transform
                    elif camera_pair.other_camera_id in transform_to_principal_camera_by_camera:
                        other_to_principal = transform_to_principal_camera_by_camera[camera_pair.other_camera_id]
                        transform_to_principal_camera_by_camera[
                            camera_pair.base_camera_id] = other_to_principal @ transform.get_inverse()

        logger.debug(
            f"Camera ID to principal camera transform estimates: {transform_to_principal_camera_by_camera}")

        return transform_to_principal_camera_by_camera

if __name__ == "__main__":
    import pickle
    pickle_path = r"C:\Users\jonma\github_repos\freemocap_organization\freemocap\freemocap\saved_mc_calib.pkl"
    loaded:MultiCameraCalibrator = pickle.load(open(pickle_path, "rb"))
    loaded.run_multi_camera_optimization()
    print(loaded)

    # save out
    with open(pickle_path, "wb") as f:
        pickle.dump(loaded, f)