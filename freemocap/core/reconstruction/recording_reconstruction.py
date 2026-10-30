"""Inputs and results at the recording-wide skeleton reconstruction boundary."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from skellyforge.core.skeleton.pose.model_scale_fitting import ModelScaleFit

from freemocap.core.reconstruction.posthoc_timing import PosthocTimingReport
from freemocap.core.reconstruction.recording_fit import RecordingFitInputs
from freemocap.core.recording.data_descriptors.recording_model import RecordedModel
from freemocap.core.data_tensors import DataTensor
from freemocap.core.types.channel_kind import ChannelKind
from freemocap.core.skeletons.tracked_skeleton_bundle import TrackedSkeletonBundle


@dataclass(frozen=True, slots=True)
class RecordingReconstructionInput:
    bundles: tuple[TrackedSkeletonBundle, ...]
    keypoint_names: tuple[str, ...]
    keypoints_3d: NDArray[np.float64]
    compute_center_of_mass: bool
    timing: PosthocTimingReport
    measured_support: NDArray[np.bool_] | None = None

    @property
    def scale_points(self) -> NDArray[np.float64]:
        if self.measured_support is None:
            return self.keypoints_3d
        return np.where(self.measured_support[..., None], self.keypoints_3d, np.nan)

    @property
    def frame_count(self) -> int:
        return self.keypoints_3d.shape[0]

    def fit_inputs(self, bundle: TrackedSkeletonBundle) -> RecordingFitInputs:
        return RecordingFitInputs.from_points(
            names=self.keypoint_names,
            values=self.keypoints_3d,
            measured_support=self.measured_support,
            model=RecordedModel.from_bundle(bundle),
        )

    def __post_init__(self) -> None:
        if (
            self.keypoints_3d.ndim != 3
            or self.keypoints_3d.shape[1:] != (len(self.keypoint_names), 3)
            or self.frame_count < 1
        ):
            raise ValueError("Expected a nonempty (frames, keypoints, 3) recording")
        if self.measured_support is not None:
            if self.measured_support.dtype != np.bool_ or self.measured_support.shape != self.keypoints_3d.shape[:2]:
                raise ValueError("Measurement support must match frame and keypoint axes")
            if np.any(self.measured_support & ~np.isfinite(self.keypoints_3d).all(axis=-1)):
                raise ValueError("Measured support cannot name absent coordinates")
        if np.isinf(self.keypoints_3d).any():
            raise ValueError("Reconstruction input cannot contain infinite coordinates")
        if len(set(self.keypoint_names)) != len(self.keypoint_names):
            raise ValueError("Keypoint names must be unique")
        if not self.bundles or len({bundle.model_id for bundle in self.bundles}) != len(
            self.bundles
        ):
            raise ValueError(
                "Recording reconstruction requires unique bundle model IDs"
            )


@dataclass(frozen=True, slots=True)
class ModelRecordingReconstruction:
    """Dense recording channels; sample positions bind to existing timing on save."""

    fit_inputs: RecordingFitInputs
    compute_center_of_mass: bool
    model_id: str
    channel_tensors: tuple[DataTensor, ...]
    scale_fit: ModelScaleFit | None
    residual_reference: str = "recording_fit"

    def __post_init__(self) -> None:
        from freemocap.core.recording.sample_encoding.reconstruction_samples import model_source_name
        if not isinstance(self.model_id, str) or not self.model_id.strip():
            raise ValueError("Reconstruction model ID must be nonempty")
        if not self.channel_tensors:
            raise ValueError("Reconstruction requires declared channel tensors")
        layouts = tuple(tensor.tensor_layout for tensor in self.channel_tensors)
        expected_axes = ("sample_position", "entity_identity", "component_identity")
        for tensor, layout in zip(self.channel_tensors, layouts, strict=True):
            if tuple(axis.axis_name for axis in layout.axes) != expected_axes:
                raise ValueError("Reconstruction requires sample, entity and component axes in that order")
            if not tensor.is_immutable:
                raise ValueError("Reconstruction channel tensors must be published immutable data")
            if tensor.data_values.dtype != np.float64:
                raise ValueError("Reconstruction channels must retain float64 precision")
            if layout.channel_kind not in tuple(ChannelKind):
                raise ValueError("Reconstruction channel kind must be declared")
            if not any(item.metadata_name == "entry_presence" for item in tensor.companion_tensors):
                raise ValueError("Reconstruction channels require explicit entry presence")
        if len({layout.channel_kind for layout in layouts}) != len(layouts):
            raise ValueError("Reconstruction channel kinds must be unique")
        first_axis = layouts[0].axes[0]
        if not first_axis.identifiers:
            raise ValueError("Reconstruction requires nonempty sample positions")
        source = layouts[0].source_identity
        if source is None or source.model_id != self.model_id or source.source_id != model_source_name(self.model_id):
            raise ValueError("Reconstruction channel belongs to another model source")
        for layout in layouts:
            if layout.axes[0] != first_axis:
                raise ValueError("Reconstruction channels must share sample positions")
            if layout.source_identity != source:
                raise ValueError("Reconstruction channels must share one model source identity")

    @property
    def frame_count(self) -> int:
        return self.channel_tensors[0].data_values.shape[0]

    def channel_tensor(self, channel_kind: str) -> DataTensor:
        for tensor in self.channel_tensors:
            if tensor.tensor_layout.channel_kind == channel_kind:
                return tensor
        raise KeyError(channel_kind)
