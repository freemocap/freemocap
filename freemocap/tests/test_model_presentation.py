"""The shared model projection carries saved geometry without inventing legacy overlays."""
from dataclasses import asdict
import numpy as np
import pytest
from skellyforge.core.skeleton.skeleton_definition import SkeletonDefinition
from skellyforge.core.skeleton.skeleton_snapshot import SkeletonSnapshot
from skellyforge.core.skeleton.pose.rest_pose import RestPose
from skellyforge.core.skeleton.components.color_palette import ColorPalette
from freemocap.core.streaming.message_model import ModelDefinition


def project(skeleton):
    return ModelDefinition.from_skeleton(model_id='test', skeleton=skeleton,
        rest_pose=RestPose.from_default_yaml(skeleton=skeleton), palette=ColorPalette.from_default_yaml(),
        scale_reference_name='body_height').to_cbor_message()


def test_saved_model_uses_identical_static_projection():
    current = SkeletonDefinition.from_default_yaml()
    saved = asdict(SkeletonSnapshot.capture(current))
    restored = SkeletonSnapshot.from_dict(saved).restore()
    assert project(current) == project(restored)
    wire = project(restored)
    assert len(wire['presentation']['attached_lines'][0]['positions']) == 1920
    assert len(wire['presentation']['attached_lines'][0]['surfaces']) == 2
    assert wire['presentation']['attached_lines'][0]['material'] == asdict(current.presentation_lines[0].material)
    assert ['thoracic', 'left_clavicle'] in wire['connections']  # hierarchy is not rewritten
    saved.pop('presentation')
    assert 'presentation' not in project(SkeletonSnapshot.from_dict(saved).restore())


@pytest.mark.parametrize('detector', ['mediapipe', 'rtmpose', 'rtmw_mediapipe_hands'])
def test_chest_mapping_matches_authored_reference_after_rigid_transform_and_scaling(detector):
    """Cross-repository calibration belongs in Core, never Tracker importing Forge.

    Mapping coefficients are dot(target - shoulder midpoint, body axis) / width.
    The body axes include the hip-to-shoulder tilt; scaling Y alone is incorrect.
    This checks the reference calibration, not zero fitting residual in every pose.
    """
    from freemocap.core.tasks.mocap.tracker_mappings import load_standard_human_mapping
    from skellytracker.core.io.prepared_tracker_mapping import PreparedTrackerMapping
    skeleton = SkeletonDefinition.from_default_yaml()
    rest = RestPose.from_default_yaml(skeleton=skeleton)
    points = {f'{side}_{key}': rest.landmark_positions[f'{side}_{landmark}'].array
              for side in ('left', 'right')
              for key, landmark in [('shoulder', 'acromion'), ('hip', 'hip_socket')]}
    rotation = np.array([[0., -1., 0.], [0., 0., -1.], [1., 0., 0.]])
    translation = np.array([123., -456., 789.])
    mapping = load_standard_human_mapping(detector)
    names = tuple(points)
    prepared = PreparedTrackerMapping.prepare(mapping, tracker_names=names)
    for scale in (1200., 1700., 2100.):
        observed = {name: scale * rotation @ point + translation for name, point in points.items()}
        mapped = mapping.apply(tracker_positions=observed)
        batch = prepared.apply(tracker_names=names, positions=np.array([[observed[n] for n in names]]))
        for name in ('left_sternoclavicular', 'right_sternoclavicular',
                     'sternoclavicular_notch', 'xiphoid_process'):
            expected = scale * rotation @ rest.landmark_positions[name].array + translation
            np.testing.assert_allclose(mapped[name], expected, rtol=0, atol=1e-6, err_msg=name)
            column = batch.landmark_names.index(name)
            assert batch.present[0, column]
            np.testing.assert_allclose(batch.positions[0, column], expected, rtol=0, atol=1e-6, err_msg=name)

@pytest.mark.parametrize('detector', ['mediapipe', 'rtmpose', 'rtmw_mediapipe_hands'])
def test_tracker_topology_survives_recording_and_shared_composition(detector):
    from freemocap.core.skeletons.standard_human_skeleton import build_standard_human_bundle
    from freemocap.core.recording.data_descriptors.recording_model import RecordedModel
    from freemocap.core.streaming.message_composer import compose_messages
    from freemocap.core.streaming.producers.producer_contexts import StreamContext
    from skellytracker.core.io.tracker_profiles import tracker_profile
    bundle = build_standard_human_bundle(detector_type=detector)
    saved = RecordedModel.from_bundle(bundle)
    restored = RecordedModel.model_validate_json(saved.model_dump_json()).to_bundle()
    def wire(value):
        return compose_messages(StreamContext(skeletons=(value,))).models[0].to_cbor_message()
    assert wire(bundle) == wire(restored)
    assert bundle.tracker_connections == tracker_profile(detector).connections
    face_edges = [(a,b) for a,b in bundle.tracker_connections if a.startswith('face_') and b.startswith('face_')]
    assert face_edges
    assert all(a in bundle.tracker_keypoint_names and b in bundle.tracker_keypoint_names for a,b in face_edges)
    legacy = saved.model_dump()
    legacy.pop('tracker_connections')
    old = RecordedModel.model_validate(legacy)
    assert old.to_bundle().tracker_connections == ()
    assert 'tracker_connections' not in old.model_dump()
    assert 'tracker_connections' not in wire(old.to_bundle())
