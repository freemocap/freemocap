"""Resolved scientific inputs for reconstructing a recorded skeleton instance."""

from pydantic import BaseModel, ConfigDict, model_serializer, model_validator
from skellyforge.core.biomechanics.center_of_mass import CenterOfMassDefinitions
from skellyforge.core.skeleton.skeleton_snapshot import (
    SkeletonSnapshot,
    RestPoseSnapshot,
)
from skellytracker.core.io.tracker_mapping import TrackerMappingSnapshot
from skellytracker.core.io.composite_tracker_mapping import CompositeTrackerMapping

from freemocap.core.skeletons.tracked_skeleton_bundle import TrackedSkeletonBundle


class RecordedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    model_id: str
    detector_type: str
    tracker_keypoint_names: tuple[str, ...]
    skeleton: SkeletonSnapshot
    rest_pose: RestPoseSnapshot
    mappings: tuple[TrackerMappingSnapshot, ...]
    center_of_mass: CenterOfMassDefinitions
    segment_masses: dict[str, float]
    scale_reference_name: str
    anchor_segment_name: str | None = None

    @model_serializer(mode="wrap")
    def serialize_model(self, handler):
        """Preserve historical fingerprints for absent observation frames.

        Old snapshots did not have this field. Absence still means no declared
        observation frame; never substitute today's model defaults. Present
        definitions must be serialized so they participate in fit signatures.
        """
        result = handler(self)
        for segment in result.get("skeleton", {}).get("segments", ()):
            if segment.get("observation_frame") is None:
                segment.pop("observation_frame", None)
        return result

    @model_validator(mode="after")
    def validate_inputs(self) -> "RecordedModel":
        if (
            not self.model_id
            or not self.detector_type
            or not self.scale_reference_name
            or not self.mappings
        ):
            raise ValueError(
                "Recorded model identity, mappings and scale reference are required"
            )
        if not self.tracker_keypoint_names or len(
            set(self.tracker_keypoint_names)
        ) != len(self.tracker_keypoint_names):
            raise ValueError("Recorded tracker keypoints must be nonempty and unique")
        if set(self.segment_masses) != set(
            self.center_of_mass.all_segment_names
        ) or any(value <= 0.0 for value in self.segment_masses.values()):
            raise ValueError(
                "Positive masses must cover the center-of-mass definitions"
            )
        return self

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, RecordedModel) and self.model_dump() == other.model_dump()
        )

    @classmethod
    def from_bundle(cls, bundle: TrackedSkeletonBundle) -> "RecordedModel":
        return cls(
            model_id=bundle.model_id,
            detector_type=bundle.detector_type,
            tracker_keypoint_names=bundle.tracker_keypoint_names,
            skeleton=SkeletonSnapshot.capture(bundle.skeleton),
            rest_pose=RestPoseSnapshot.capture(bundle.rest_pose),
            mappings=bundle.landmark_mapping.mapping_snapshots(),
            center_of_mass=bundle.center_of_mass_definitions,
            segment_masses=dict(bundle.segment_masses),
            scale_reference_name=bundle.scale_reference_name,
            anchor_segment_name=bundle.anchor_segment_name,
        )

    def to_bundle(self) -> TrackedSkeletonBundle:
        skeleton = self.skeleton.restore()
        self.center_of_mass.validate_against(skeleton=skeleton)
        return TrackedSkeletonBundle(
            model_id=self.model_id,
            detector_type=self.detector_type,
            tracker_keypoint_names=self.tracker_keypoint_names,
            skeleton=skeleton,
            rest_pose=self.rest_pose.restore(skeleton),
            landmark_mapping=CompositeTrackerMapping(
                mappings=tuple(item.restore() for item in self.mappings)
            ),
            center_of_mass_definitions=self.center_of_mass,
            segment_masses=dict(self.segment_masses),
            scale_reference_name=self.scale_reference_name,
            anchor_segment_name=self.anchor_segment_name,
        )
