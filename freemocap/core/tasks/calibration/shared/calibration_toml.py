"""Calibration TOML storage and historical-format conversion."""

from typing import Self

import cv2
import numpy as np
import tomli_w
from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    FiniteFloat,
    PositiveFloat,
    TypeAdapter,
    field_validator,
    model_validator,
)
from skellytracker.core.detectors.keypoint_detectors.charuco import CharucoBoardDefinition

from freemocap.core.tasks.calibration.shared.calibration_metadata import CalibrationMetadata
from freemocap.core.tasks.calibration.shared.camera_extrinsics import CameraExtrinsics
from freemocap.core.tasks.calibration.shared.camera_intrinsics import CameraIntrinsics
from freemocap.core.tasks.calibration.shared.camera_model import CameraModel
from freemocap.utilities.toml_mixin import TomlMixin


TomlVector3 = tuple[FiniteFloat, FiniteFloat, FiniteFloat]
TomlMatrix3 = tuple[TomlVector3, TomlVector3, TomlVector3]


_TABLE = TypeAdapter(dict[str, object])
_INTEGER = TypeAdapter(int)
_FINITE_FLOAT = TypeAdapter(FiniteFloat)
_POSITIVE_FLOAT = TypeAdapter(PositiveFloat)


def _read_legacy_board(value: object) -> CharucoBoardDefinition:
    """Translate retired file fields into the existing board definition."""
    if isinstance(value, CharucoBoardDefinition):
        return value
    raw = _TABLE.validate_python(value)
    # These are historical file defaults, not a new calibration-board preset.
    defaults = CharucoBoardDefinition(squares_x=7, squares_y=5, square_length_mm=1.0)
    fields = {
        name: raw[name]
        for name in CharucoBoardDefinition.model_fields
        if name in raw
    }
    if raw.get("aruco_dictionary_enum") is None:
        legacy_dictionaries = {
            (4, 50): cv2.aruco.DICT_4X4_50,
            (4, 100): cv2.aruco.DICT_4X4_100,
            (4, 250): cv2.aruco.DICT_4X4_250,
            (4, 1000): cv2.aruco.DICT_4X4_1000,
            (5, 50): cv2.aruco.DICT_5X5_50,
            (5, 100): cv2.aruco.DICT_5X5_100,
            (5, 250): cv2.aruco.DICT_5X5_250,
            (5, 1000): cv2.aruco.DICT_5X5_1000,
        }
        fields["aruco_dictionary_enum"] = legacy_dictionaries.get(
            (
                _INTEGER.validate_python(raw.get("marker_bits", 4)),
                _INTEGER.validate_python(raw.get("dict_size", 250)),
            ),
            defaults.aruco_dictionary_enum,
        )
    marker_length = raw.get("marker_length_mm", raw.get("aruco_marker_length_mm"))
    if raw.get("marker_length_ratio") is None:
        fields.pop("marker_length_ratio", None)
        if marker_length is not None:
            fields["marker_length_ratio"] = (
                _FINITE_FLOAT.validate_python(marker_length)
                / _POSITIVE_FLOAT.validate_python(
                    raw.get("square_length_mm", defaults.square_length_mm),
                )
            )
    return CharucoBoardDefinition.model_validate({
        **defaults.model_dump(round_trip=True),
        **fields,
    })


def _read_legacy_metadata(value: object) -> CalibrationMetadata:
    """Supply historical defaults without introducing another metadata schema."""
    if isinstance(value, CalibrationMetadata):
        return value
    raw = _TABLE.validate_python(value)
    for current, historical in (
        ("aligned", ("groundplane_applied", "groundplane_aligned")),
        ("alignment_method", ("groundplane_method",)),
        ("alignment_recording_id", ("groundplane_recording_id",)),
        ("alignment_result", ("groundplane_result",)),
    ):
        if current not in raw:
            for old_name in historical:
                if old_name in raw:
                    raw[current] = raw[old_name]
                    break
    defaults = CalibrationMetadata(
        board=_read_legacy_board(raw.get("board", {})),
        reprojection_error_px=0.0,
        initial_cost=0.0,
        final_cost=0.0,
        n_iterations=0,
        time_seconds=0.0,
        n_observations_used=0,
        n_observations_rejected=0,
    )
    fields = defaults.model_dump(by_alias=True, round_trip=True)
    # Retain the old loader's handling of unknown historical fields, but derive
    # the accepted names and aliases from the authoritative metadata model.
    for name, field in CalibrationMetadata.model_fields.items():
        key = field.alias or name
        if key in raw:
            fields[key] = raw[key]
        elif name in raw:
            fields[key] = raw[name]
    fields["board"] = defaults.board
    return CalibrationMetadata.model_validate(fields)


class CameraToml(BaseModel):
    """Camera file representation, converted through the existing camera factories."""

    model_config = ConfigDict(extra="ignore")

    name: str
    id: str | None = None
    index: int | None = None
    size: tuple[int, int] = Field(validation_alias=AliasChoices("size", "image_size"))
    matrix: TomlMatrix3
    distortions: tuple[FiniteFloat, ...]
    rotation: TomlVector3
    translation: TomlVector3
    world_orientation: TomlMatrix3 | None = None
    world_position: TomlVector3 | None = None

    @classmethod
    def from_camera(cls, camera: CameraModel) -> Self:
        return cls(
            name=camera.id,
            id=camera.id,
            index=camera.index,
            size=camera.image_size,
            matrix=camera.intrinsics.to_camera_matrix().tolist(),
            distortions=camera.intrinsics.to_dist_coeffs_5().tolist(),
            rotation=camera.extrinsics.rodrigues_vector.tolist(),
            translation=camera.extrinsics.translation.tolist(),
            world_orientation=camera.extrinsics.world_orientation.tolist(),
            world_position=camera.extrinsics.world_position.tolist(),
        )

    def to_camera(self, *, default_index: int) -> CameraModel:
        intrinsics = CameraIntrinsics.from_camera_matrix_and_dist(
            camera_matrix=np.asarray(self.matrix, dtype=np.float64),
            dist_coeffs=np.asarray(self.distortions, dtype=np.float64),
        )
        extrinsics = CameraExtrinsics.from_rodrigues(
            rvec=np.asarray(self.rotation, dtype=np.float64),
            tvec=np.asarray(self.translation, dtype=np.float64),
        )
        return CameraModel(
            id=self.name if self.id is None else self.id,
            index=default_index if self.index is None else self.index,
            image_size=self.size,
            intrinsics=intrinsics,
            extrinsics=extrinsics,
            world_position=(
                extrinsics.world_position if self.world_position is None
                else np.asarray(self.world_position, dtype=np.float64)
            ),
            world_orientation=(
                extrinsics.world_orientation if self.world_orientation is None
                else np.asarray(self.world_orientation, dtype=np.float64)
            ),
        )


class CalibrationToml(BaseModel, TomlMixin):
    """One metadata table plus camera tables named by camera ID."""

    model_config = ConfigDict(extra="allow")

    __pydantic_extra__: dict[str, CameraToml] = Field(init=False)
    metadata: CalibrationMetadata = Field(
        default_factory=lambda: _read_legacy_metadata({}),
    )

    @field_validator("metadata", mode="before")
    @classmethod
    def read_metadata(cls, value: object) -> CalibrationMetadata:
        return _read_legacy_metadata(value)

    @model_validator(mode="after")
    def require_cameras(self) -> Self:
        if not self.__pydantic_extra__:
            raise ValueError("Calibration TOML must contain at least one camera")
        return self

    @classmethod
    def from_calibration(
        cls, *, cameras: list[CameraModel], metadata: CalibrationMetadata,
    ) -> Self:
        camera_ids = [camera.id for camera in cameras]
        if len(set(camera_ids)) != len(camera_ids):
            raise ValueError("Calibration camera IDs must be unique")
        if any(camera_id in cls.model_fields for camera_id in camera_ids):
            raise ValueError("A camera ID conflicts with a reserved calibration TOML table")
        return cls(
            metadata=metadata,
            **{camera.id: CameraToml.from_camera(camera) for camera in cameras},
        )

    def to_cameras(self) -> list[CameraModel]:
        return [
            self.__pydantic_extra__[key].to_camera(default_index=index)
            for index, key in enumerate(sorted(self.__pydantic_extra__))
        ]

    def model_dump_toml(self) -> str:
        return tomli_w.dumps(self.model_dump(
            mode="json", by_alias=True, exclude_none=True, round_trip=True,
        ))
