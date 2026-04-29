from pathlib import Path

import numpy as np
import toml
from freemocap.core.tasks.calibration.charuco.charuco_board import CharucoBoardDefinition
from freemocap.core.tasks.calibration.shared.camera_intrinsics import CameraIntrinsics
from freemocap.core.tasks.calibration.shared.camera_extrinsics import CameraExtrinsics
from freemocap.core.tasks.calibration.shared.camera_model import CameraModel
from freemocap.utilities.toml_mixin import TomlMixin, numpy_to_python
from pydantic import BaseModel, ConfigDict
from skellycam.core.types.type_overloads import CameraIdString, CameraIndexInt


class CalibrationResult(BaseModel, TomlMixin):
    """Output of either calibration pipeline.

    Both the anipose and pyceres paths produce this type. It can be
    serialized to/from the anipose-compatible TOML format.

    Provides get_triangulator() and get_triangulator_for_cameras() to
    build a Triangulator for downstream 3D reconstruction without any
    anipose dependency.
    """

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    cameras: list[CameraModel]
    board: CharucoBoardDefinition
    reprojection_error_px: float
    initial_cost: float
    final_cost: float
    n_iterations: int
    time_seconds: float
    n_observations_used: int
    n_observations_rejected: int
    groundplane_aligned: bool = False

    @property
    def camera_ids(self) -> list[str]:
        return [c.id for c in self.cameras]

    def get_camera(self, camera_id: str) -> CameraModel:
        """Look up a camera by name."""
        for cam in self.cameras:
            if cam.id == camera_id:
                return cam
        raise KeyError(f"Camera '{camera_id}' not found. Available: {self.camera_ids}")

    # ---- Triangulator construction ----

    def get_triangulator(self) -> "Triangulator":
        """Build a Triangulator from this calibration's cameras.

        The Triangulator performs DLT triangulation directly from CameraModel
        intrinsics/extrinsics with no anipose dependency.
        """
        from freemocap.core.tasks.triangulation.triangulator import Triangulator

        return Triangulator.from_calibration_result(calibration=self)

    def get_triangulator_for_cameras(self, camera_ids: list[str]) -> "Triangulator":
        """Build a Triangulator with cameras ordered to match the given IDs.

        Use this when the current session's cameras may be a subset of,
        or in a different order than, the calibration's cameras.

        Raises:
            KeyError: If any camera_id is not found in this calibration.
        """
        from freemocap.core.tasks.triangulation.triangulator import Triangulator

        return Triangulator.from_calibration_for_cameras(
            calibration=self,
            camera_ids=camera_ids,
        )

    # ---- Anipose-compatible TOML (same as existing) ----

    def dump_anipose_toml(
            self,
            path: Path,
            metadata: dict | None = None,
    ) -> None:
        """Write anipose-compatible TOML."""
        cameras_dict: dict[str, object] = {}

        for cam in self.cameras:
            cameras_dict[cam.id] = {
                "name": cam.id,
                "id": cam.id,
                "index": cam.index,
                "size": list(cam.image_size),
                "matrix": cam.intrinsics.to_camera_matrix().tolist(),
                "distortions": cam.intrinsics.to_dist_coeffs_5().tolist(),
                "rotation": cam.extrinsics.rodrigues_vector.tolist(),
                "translation": cam.extrinsics.translation.tolist(),
                "world_orientation": cam.extrinsics.world_orientation.tolist(),
                "world_position": cam.extrinsics.world_position.tolist(),
            }

        meta = metadata.copy() if metadata else {}
        meta["reprojection_error_px"] = self.reprojection_error_px
        meta["n_observations_used"] = self.n_observations_used
        meta["n_observations_rejected"] = self.n_observations_rejected
        meta["solver_time_seconds"] = self.time_seconds
        meta["board"] = {
            "squares_x": self.board.squares_x,
            "squares_y": self.board.squares_y,
            "square_length_mm": self.board.square_length_mm,
            "marker_length_mm": self.board.aruco_marker_length_mm,
            "marker_bits": self.board.marker_bits,
            "dict_size": self.board.dict_size,
        }
        cameras_dict["metadata"] = numpy_to_python(meta)

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(toml.dumps(cameras_dict))

    @classmethod
    def load_anipose_toml(cls, path: Path) -> "CalibrationResult":
        """Load from an anipose-compatible TOML calibration file."""
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(f"Calibration file not found: {path}")

        toml_data = toml.load(path)
        metadata = toml_data.pop("metadata", {})

        cameras: list[CameraModel] = []
        for key in sorted(toml_data.keys()):
            d = toml_data[key]
            if "name" not in d:
                raise ValueError(f"TOML key '{key}' missing 'name' field")

            if "size" in d:
                size = (int(d["size"][0]), int(d["size"][1]))
            elif "image_size" in d:
                size = (int(d["image_size"][0]), int(d["image_size"][1]))
            else:
                raise KeyError(f"Camera '{key}' missing 'size' or 'image_size'")

            K = np.array(d["matrix"], dtype=np.float64)
            if K.shape != (3, 3):
                raise ValueError(f"Camera '{key}': matrix shape {K.shape}, expected (3, 3)")

            dist = np.array(d["distortions"], dtype=np.float64).ravel()

            intrinsics = CameraIntrinsics(
                fx=float(K[0, 0]),
                fy=float(K[1, 1]),
                cx=float(K[0, 2]),
                cy=float(K[1, 2]),
                k1=float(dist[0]) if len(dist) > 0 else 0.0,
                k2=float(dist[1]) if len(dist) > 1 else 0.0,
                p1=float(dist[2]) if len(dist) > 2 else 0.0,
                p2=float(dist[3]) if len(dist) > 3 else 0.0,
            )

            rvec = np.array(d["rotation"], dtype=np.float64).ravel()
            tvec = np.array(d["translation"], dtype=np.float64).ravel()
            extrinsics = CameraExtrinsics.from_rodrigues(rvec=rvec, tvec=tvec)

            camera_id = d.get("id", None)
            if camera_id is None:
                camera_id = d.get("name", None)

            cameras.append(
                CameraModel(
                    id=CameraIdString(camera_id),
                    index=CameraIndexInt(d["index"]),
                    image_size=size,
                    intrinsics=intrinsics,
                    extrinsics=extrinsics,
                )
            )

        if len(cameras) == 0:
            raise ValueError(f"No cameras found in {path}")

        board_meta = metadata.get("board", {})
        board = CharucoBoardDefinition(
            squares_x=board_meta.get("squares_x", 7),
            squares_y=board_meta.get("squares_y", 5),
            square_length_mm=board_meta.get("square_length_mm", 1.0),
            # aruco_marker_length_mm=board_meta.get("marker_length_mm", 0.8),
            marker_bits=board_meta.get("marker_bits", 4),
            dict_size=board_meta.get("dict_size", 250),
        )

        return cls(
            cameras=cameras,
            board=board,
            reprojection_error_px=metadata.get("reprojection_error_px", 0.0),
            initial_cost=metadata.get("initial_cost", 0.0),
            final_cost=metadata.get("final_cost", 0.0),
            n_iterations=metadata.get("n_iterations", 0),
            time_seconds=metadata.get("solver_time_seconds", 0.0),
            n_observations_used=metadata.get("n_observations_used", 0),
            n_observations_rejected=metadata.get("n_observations_rejected", 0),
            groundplane_aligned=metadata.get("groundplane_applied", False),
        )
