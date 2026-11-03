"""Connect Tracker's named DLC measurements to Forge's rigid-object geometry."""
import hashlib
from pathlib import Path

from skellyforge.core.biomechanics.center_of_mass import CenterOfMassDefinitions
from skellyforge.core.skeleton.pose.rest_pose import RestPose
from skellyforge.core.skeleton.stl_rigid_body import load_stl_rigid_body
from skellytracker.core.io.tracker_mapping import TrackerMapping
from skellytracker.core.tracker.tracker_presets import dlc_tracker_metadata

from freemocap.core.skeletons.rigid_object_geometry import RigidObjectGeometry
from freemocap.core.skeletons.tracked_skeleton_bundle import TrackedSkeletonBundle


def build_dlc_object_bundle(*, sidecar_path: str | Path, geometry_path: str | Path) -> TrackedSkeletonBundle:
    metadata = dlc_tracker_metadata(sidecar_path=sidecar_path)
    path = Path(geometry_path).expanduser().resolve()
    model_id = "dlc_object_" + hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    definition = load_stl_rigid_body(path=path, name=model_id)
    if definition.feature_names != metadata.keypoint_names:
        raise ValueError("DLC geometry feature names and order must exactly match the selected detector sidecar")
    skeleton = definition.skeleton
    return TrackedSkeletonBundle(
        model_id=model_id, detector_type="dlc", tracker_keypoint_names=metadata.keypoint_names,
        tracker_connections=metadata.connections, skeleton=skeleton,
        rest_pose=RestPose.default_for(skeleton=skeleton),
        landmark_mapping=TrackerMapping(entries={}, known_tracker_keypoints=set(metadata.keypoint_names),
                                       passthrough_keypoints_as_landmarks=True),
        center_of_mass_definitions=CenterOfMassDefinitions.default_for(skeleton=skeleton),
        segment_masses={definition.segment_name: 1.0}, scale_reference_name=definition.scale_reference_name,
        object_geometry=RigidObjectGeometry.from_definition(definition),
        tracker_stage_path=metadata.stage_path,
    )
