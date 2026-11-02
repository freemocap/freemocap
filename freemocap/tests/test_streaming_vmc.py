"""Independent receiver transforms, immutable measurement times and real UDP wire."""
from dataclasses import replace
from importlib.resources import files
import json
import os
from pathlib import Path
import socket
import struct

import numpy as np
import pytest
from scipy.spatial.transform import Rotation
from pydantic import ValidationError
from skellyforge.core.skeleton.skeleton_definition import SkeletonDefinition
from skellyforge.core.skeleton.pose.rest_pose import RestPose
from skellyforge.core.skeleton.components.color_palette import ColorPalette

from freemocap.core.streaming.message_model import (
    ChannelBlock, ChannelKind, FrameMessage, MessageEnvelope, ModelDefinition,
    ModelInstance,
)
from freemocap.core.streaming.outputs.contracts import OutputSample
from freemocap.core.streaming.outputs.vmc import (
    BODY_BINDINGS, FINGER_BINDINGS, VmcConfig, VmcEmitter, VmcProjector,
    osc_bundles, osc_message,
)


@pytest.fixture(scope="module")
def human():
    skeleton = SkeletonDefinition.from_default_yaml()
    rest = RestPose.from_default_yaml(skeleton=skeleton)
    model = ModelDefinition.from_skeleton(
        model_id="standard_human", skeleton=skeleton, rest_pose=rest,
        palette=ColorPalette.from_default_yaml(), scale_reference_name="body_height",
    )
    return model, rest


def sample_frame(human, *, timestamp=9_100_000_000_000_123, perturb=False):
    model, rest = human
    origins = np.asarray([rest.segment_origins[s.name].array * 1700 for s in model.segments])
    matrices = np.asarray([rest.segment_orientations[s.name].to_rotation_matrix() for s in model.segments])
    if perturb:
        global_rotation = Rotation.from_euler("z", 37, degrees=True).as_matrix()
        matrices = global_rotation @ matrices
        origins = origins @ global_rotation.T + np.array([123., -456., 72.])
        for i, segment in enumerate(model.segments):
            if segment.name in ("left_upper_arm", "left_lower_arm"):
                matrices[i] = Rotation.from_euler("xy", [23., -39.], degrees=True).as_matrix() @ matrices[i]
    xyzw = Rotation.from_matrix(matrices).as_quat()
    channels = (
        ChannelBlock(ChannelKind.SEGMENT_ORIGINS, ("x", "y", "z"), origins.astype("<f4").tobytes()),
        ChannelBlock(ChannelKind.ROTATIONS_WORLD, ("w", "x", "y", "z"), xyzw[:, [3, 0, 1, 2]].astype("<f4").tobytes()),
    )
    frame = FrameMessage(envelope=MessageEnvelope(timestamp=float(timestamp)), models=(model,),
                         instances=(ModelInstance(0, model.model_id, channels, 1700.),))
    return OutputSample(frame=frame, pipeline_id="capture-a", source_timestamp_ns=timestamp,
                        camera_timestamps_ns=(("camera-a", timestamp),))


def independent_reference():
    text = files("skellyforge").joinpath("definitions/human_skeleton/default-vrm.gltf.json5").read_text()
    nodes = json.loads(text[text.index("{"):])["nodes"]
    parents = {child: i for i, node in enumerate(nodes) for child in node.get("children", [])}
    world = {}
    def resolve(i):
        if i not in world:
            rotation = Rotation.from_quat(nodes[i].get("rotation", [0, 0, 0, 1])).as_matrix()
            world[i] = resolve(parents[i]) @ rotation if i in parents else rotation
        return world[i]
    for i in range(len(nodes)):
        resolve(i)
    return {node["name"]: world[i] for i, node in enumerate(nodes)}


@pytest.mark.parametrize("include_fingers", [False, True])
@pytest.mark.parametrize("perturb", [False, True])
def test_original_reference_rest_and_asymmetric_pose_reconstruct(human, include_fingers, perturb):
    sample = sample_frame(human, perturb=perturb)
    before = tuple(c.data for c in sample.frame.instances[0].channels)
    projector = VmcProjector(VmcConfig(include_fingers=include_fingers, profile="forge_reference_vrm_original"))
    pose = projector.project(sample.frame, sample.source_timestamp_ns)
    assert pose is not None
    assert pose.source_timestamp_ns == 9_100_000_000_000_123
    assert tuple(c.data for c in sample.frame.instances[0].channels) == before
    assert pose.bone_names == tuple(b[1] for b in BODY_BINDINGS + (FINGER_BINDINGS if include_fingers else ()))
    reference = independent_reference()
    # Independent axis permutations, not the transform under test.
    source_to_unity = np.array([[1., 0, 0], [0, 0, 1], [0, 1, 0]])
    asset_to_unity = np.diag([-1., 1., 1.])
    source_quats = np.frombuffer(before[1], dtype="<f4").reshape(-1, 4)
    source_matrices = Rotation.from_quat(source_quats[:, [1, 2, 3, 0]]).as_matrix()
    source_origins = np.frombuffer(before[0], dtype="<f4").reshape(-1, 3)
    model, rest = human
    source_rows = {segment.name: i for i, segment in enumerate(model.segments)}
    world, positions = {}, {}
    for row, (source, target, node) in enumerate(projector.bindings):
        parent = projector.parents[row]
        local = Rotation.from_quat(pose.local_quaternions_xyzw[row]).as_matrix()
        parent_rotation = np.eye(3) if parent < 0 else world[int(parent)]
        world[row] = parent_rotation @ local
        positions[row] = (pose.root_position_m if parent < 0 else positions[int(parent)]) + parent_rotation @ pose.local_positions_m[row]
        target_reference = asset_to_unity @ reference[node] @ asset_to_unity.T
        source_rest = rest.segment_orientations[source].to_rotation_matrix()
        delta_unity = source_to_unity @ source_matrices[source_rows[source]] @ source_rest.T @ source_to_unity.T
        np.testing.assert_allclose(world[row], delta_unity @ target_reference, atol=3e-6)
        np.testing.assert_allclose(positions[row], source_to_unity @ source_origins[source_rows[source]] / 1000, atol=1e-7)
    # Hips translation appears once through Root, never doubled in the bone pose.
    np.testing.assert_array_equal(pose.local_positions_m[0], [0., 0., 0.])


def test_source_world_rest_is_not_composed_as_local(human):
    sample = sample_frame(human)
    projector = VmcProjector(VmcConfig(profile="forge_reference_vrm_original"))
    pose = projector.project(sample.frame, sample.source_timestamp_ns)
    index = pose.bone_names.index("LeftLowerArm")
    # At source rest, target child LOCAL rotation equals its original asset local.
    reference = independent_reference()
    expected = reference["upper_arm.L"].T @ reference["lower_arm.L"]
    flip = np.diag([-1., 1., 1.])
    np.testing.assert_allclose(Rotation.from_quat(pose.local_quaternions_xyzw[index]).as_matrix(),
                               flip @ expected @ flip, atol=3e-6)


@pytest.mark.parametrize("include_fingers", [False, True])
@pytest.mark.parametrize("perturb", [False, True])
def test_normalized_receiver_uses_motion_from_rest_not_authored_bone_axes(human, include_fingers, perturb):
    """Recompose receiver locals independently; normalized T-pose is identity."""
    sample = sample_frame(human, perturb=perturb)
    projector = VmcProjector(VmcConfig(include_fingers=include_fingers))
    assert projector.config.profile == "vrm0_normalized"
    pose = projector.project(sample.frame, sample.source_timestamp_ns)
    assert pose is not None
    model, rest = human
    source_rows = {segment.name: i for i, segment in enumerate(model.segments)}
    quats = np.frombuffer(sample.frame.instances[0].channels[1].data, dtype="<f4").reshape(-1, 4)
    measured = Rotation.from_quat(quats[:, [1, 2, 3, 0]]).as_matrix()
    basis = np.array([[1., 0, 0], [0, 0, 1], [0, 1, 0]])
    world = {}
    for row, (source, _, _) in enumerate(projector.bindings):
        parent = projector.parents[row]
        local = Rotation.from_quat(pose.local_quaternions_xyzw[row]).as_matrix()
        world[row] = (np.eye(3) if parent < 0 else world[int(parent)]) @ local
        expected = basis @ measured[source_rows[source]] @ rest.segment_orientations[source].to_rotation_matrix().T @ basis.T
        np.testing.assert_allclose(world[row], expected, atol=3e-6)
        if not perturb:
            np.testing.assert_allclose(local, np.eye(3), atol=3e-6)
    assert pose.source_timestamp_ns == sample.source_timestamp_ns


def read_string(packet, offset):
    end = packet.index(b"\0", offset)
    return packet[offset:end].decode(), (end + 4) // 4 * 4


def decode_packet(packet):
    assert packet[:8] == b"#bundle\0"
    assert struct.unpack(">Q", packet[8:16])[0] == 1
    cursor, messages = 16, []
    while cursor < len(packet):
        size = struct.unpack_from(">I", packet, cursor)[0]
        cursor += 4
        message = packet[cursor:cursor + size]
        cursor += size
        address, pos = read_string(message, 0)
        tags, pos = read_string(message, pos)
        values = []
        for tag in tags[1:]:
            if tag == "s":
                value, pos = read_string(message, pos)
            else:
                value = struct.unpack_from(">f" if tag == "f" else ">i", message, pos)[0]
                pos += 4
            values.append(value)
        assert pos == len(message)
        messages.append((address, values))
    assert cursor == len(packet)
    return messages


def receive_frame(receiver, limit):
    messages = []
    while not messages or messages[-1][0] != "/VMC/Ext/T":
        packet, _ = receiver.recvfrom(65536)
        assert len(packet) <= limit
        messages.extend(decode_packet(packet))
    return messages


def test_real_udp_measurement_time_and_clean_close(human):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
        receiver.bind(("127.0.0.1", 0))
        receiver.settimeout(2.)
        emitter = VmcEmitter(VmcConfig(port=receiver.getsockname()[1], max_datagram_bytes=256))
        sample = sample_frame(human, perturb=True)
        try:
            emitter.emit(sample)
            first = receive_frame(receiver, 256)
            delayed = replace(sample, source_timestamp_ns=sample.source_timestamp_ns + 123_456_789)
            # No wall-clock/sleep relationship: replay may emit later immediately.
            emitter.emit(delayed)
            second = receive_frame(receiver, 256)
            assert len([m for m in first if m[0] == "/VMC/Ext/Bone/Pos"]) == 21
            assert first[-2] == ("/VMC/Ext/OK", [1])
            root = next(values for address, values in first if address == "/VMC/Ext/Root/Pos")
            assert root[0] == "root"
            np.testing.assert_allclose(root[1:], [.123, .072, -.456, 0., 0., 0., 1.], atol=2e-8)
            assert first[-1] == ("/VMC/Ext/T", [0.])
            assert second[-1][1][0] == pytest.approx(.123456789, abs=1e-8)
            assert emitter.last_source_timestamp_ns == delayed.source_timestamp_ns
            assert sample.camera_timestamps_ns[0][1] == sample.source_timestamp_ns
        finally:
            emitter.close()
            emitter.close()
        assert emitter.socket.fileno() == -1
        with pytest.raises(RuntimeError, match="closed"):
            emitter.emit(sample)


@pytest.mark.parametrize("fault", ["nan", "missing", "status"])
def test_unavailable_pose_reports_not_loaded_without_fabricated_transforms(human, fault):
    sample = sample_frame(human)
    instance = sample.frame.instances[0]
    channels = list(instance.channels)
    if fault == "nan":
        values = np.frombuffer(channels[0].data, dtype="<f4").copy()
        values[:] = np.nan
        channels[0] = replace(channels[0], data=values.tobytes())
    elif fault == "missing":
        channels.pop()
    else:
        channels[0] = replace(channels[0], sample_status=bytes(len(human[0].segments)))
    sample = replace(sample, frame=replace(sample.frame, instances=(replace(instance, channels=tuple(channels)),)))
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
        receiver.bind(("127.0.0.1", 0))
        receiver.settimeout(2.)
        emitter = VmcEmitter(VmcConfig(port=receiver.getsockname()[1]))
        try:
            emitter.emit(sample)
            assert receive_frame(receiver, 1200) == [("/VMC/Ext/OK", [0]), ("/VMC/Ext/T", [0.])]
            assert emitter.invalid_samples == 1
        finally:
            emitter.close()


@pytest.mark.parametrize("fault", ["nan", "status"])
@pytest.mark.parametrize("missing", ["left_upper_leg", "left_toes", "left_upper_arm"])
def test_partial_pose_keeps_valid_branches_without_fabricating_missing_bones(human, fault, missing):
    sample = sample_frame(human, perturb=True)
    projector = VmcProjector(VmcConfig())
    complete = projector.project(sample.frame, sample.source_timestamp_ns)
    instance = sample.frame.instances[0]
    index = next(i for i, segment in enumerate(human[0].segments) if segment.name == missing)
    channels = list(instance.channels)
    if fault == 'nan':
        data = np.frombuffer(channels[0].data, dtype='<f4').copy().reshape(-1, 3)
        data[index] = np.nan
        channels[0] = replace(channels[0], data=data.tobytes())
    else:
        status = np.ones(len(human[0].segments), dtype=np.uint8)
        status[index] = 0
        channels[1] = replace(channels[1], sample_status=status.tobytes())
    frame = replace(sample.frame, instances=(replace(instance, channels=tuple(channels)),))
    pose = projector.project(frame, sample.source_timestamp_ns)
    assert pose is not None and 'Hips' in pose.bone_names and 'Head' in pose.bone_names
    excluded = {'left_upper_leg': {'LeftUpperLeg', 'LeftLowerLeg', 'LeftFoot', 'LeftToes'},
                'left_toes': {'LeftToes'},
                'left_upper_arm': {'LeftUpperArm', 'LeftLowerArm', 'LeftHand'}}[missing]
    assert set(pose.bone_names) == set(complete.bone_names) - excluded
    rows = [complete.bone_names.index(name) for name in pose.bone_names]
    np.testing.assert_allclose(pose.local_positions_m, complete.local_positions_m[rows])
    np.testing.assert_allclose(pose.local_quaternions_xyzw, complete.local_quaternions_xyzw[rows])
    assert pose.source_timestamp_ns == sample.source_timestamp_ns


def test_partial_pose_requires_valid_root(human):
    sample = sample_frame(human)
    instance = sample.frame.instances[0]
    status = np.ones(len(human[0].segments), dtype=np.uint8)
    status[next(i for i, segment in enumerate(human[0].segments) if segment.name == 'pelvis')] = 0
    channels = (replace(instance.channels[0], sample_status=status.tobytes()), instance.channels[1])
    frame = replace(sample.frame, instances=(replace(instance, channels=channels),))
    assert VmcProjector(VmcConfig()).project(frame, sample.source_timestamp_ns) is None


def test_config_and_packet_limits_fail_loudly():
    with pytest.raises(ValidationError):
        VmcConfig(profile="arbitrary-avatar")
    with pytest.raises(ValidationError):
        VmcConfig(host="unresolved-host")
    with pytest.raises(ValidationError):
        VmcConfig(port=0)
    with pytest.raises(ValueError, match="datagram budget"):
        osc_bundles([osc_message("/x", "x" * 300)], 256)


def test_bad_quaternion_is_not_normalized_into_a_pose(human):
    sample = sample_frame(human)
    instance = sample.frame.instances[0]
    rotations = instance.channels[1]
    q = np.frombuffer(rotations.data, dtype="<f4").copy() * 2
    frame = replace(sample.frame, instances=(replace(instance, channels=(instance.channels[0], replace(rotations, data=q.tobytes()))),))
    with pytest.raises(ValueError, match="unit source"):
        VmcProjector(VmcConfig()).project(frame, sample.source_timestamp_ns)


def test_concurrent_destinations_are_independent(human):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as a, socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as b:
        a.bind(("127.0.0.1", 0))
        b.bind(("127.0.0.1", 0))
        a.settimeout(2.)
        b.settimeout(2.)
        first = VmcEmitter(VmcConfig(port=a.getsockname()[1]))
        second = VmcEmitter(VmcConfig(port=b.getsockname()[1]))
        sample = sample_frame(human)
        try:
            first.emit(sample)
            second.emit(sample)
            assert receive_frame(a, 1200) == receive_frame(b, 1200)
            first.close()
            second.emit(replace(sample, source_timestamp_ns=sample.source_timestamp_ns + 1_000_000_000))
            assert receive_frame(b, 1200)[-1] == ("/VMC/Ext/T", [1.])
            assert not second.closed
        finally:
            first.close()
            second.close()


def test_transport_failure_propagates_and_does_not_mutate_sample(human):
    emitter = VmcEmitter(VmcConfig())
    sample = sample_frame(human)
    original = sample.frame.instances[0].channels[0].data
    emitter.socket.close()  # Real failed transport, not a mocked success path.
    try:
        with pytest.raises(OSError):
            emitter.emit(sample)
        assert sample.frame.instances[0].channels[0].data is original
    finally:
        emitter.close()


def test_metadata_change_rebinds_and_missing_selection_waits(human):
    sample = sample_frame(human)
    projector = VmcProjector(VmcConfig())
    projector.project(sample.frame, sample.source_timestamp_ns)
    assert projector.project(replace(sample.frame, instances=()), sample.source_timestamp_ns) is None
    model = human[0]
    damaged = replace(model, segments=model.segments[1:])
    with pytest.raises(ValueError, match="pelvis"):
        projector.project(replace(sample.frame, models=(damaged,)), sample.source_timestamp_ns)


def test_pixel_reconstruction_is_not_interpreted_as_millimeters(human):
    from freemocap.core.diagnostics.pipeline_diagnostics import PipelineDiagnostics
    sample = sample_frame(human)
    frame = replace(sample.frame, diagnostics=PipelineDiagnostics("pixels", (), {}))
    with pytest.raises(ValueError, match="pixel-space"):
        VmcProjector(VmcConfig()).project(frame, sample.source_timestamp_ns)


@pytest.mark.parametrize("recording_id", ["freemocap_test_data", "freemocap_sample_data"])
def test_reference_recording_pose_replay(human, recording_id):
    """Existing stored channels, no reconstruction or timestamp regeneration."""
    root = os.environ.get("FREEMOCAP_VMC_REFERENCE_ROOT")
    if not root:
        pytest.skip("Set FREEMOCAP_VMC_REFERENCE_ROOT to the existing reference recordings")
    import pyarrow.parquet as pq
    from freemocap.core.recording.playback_queries import playback_manifest
    path = Path(root) / recording_id / f"{recording_id}_data.parquet"
    manifest = playback_manifest(path)
    run = next(run for run in manifest.runs if run.run_id == manifest.selected_run_id)
    model = next(model for model in run.models if model.model_id == "standard_human")
    source = next(source for source, model_id in run.model_sources.items() if model_id == model.model_id)
    data = pq.read_table(path, columns=["frame_number", "timestamp_s", "channel", "name", "component", "value"],
                         filters=[("run_id", "=", run.run_id), ("source", "=", source),
                                  ("channel", "in", ["SEGMENT_ORIGINS", "ROTATIONS_WORLD"])]).to_pydict()
    frame_numbers = sorted(set(data["frame_number"]))
    slots = {frame: index for index, frame in enumerate(frame_numbers)}
    names = {segment.name: index for index, segment in enumerate(model.segments)}
    origins = np.full((len(slots), len(names), 3), np.nan)
    rotations = np.full((len(slots), len(names), 4), np.nan)
    timestamps = {}
    for frame, timestamp, channel, name, component, value in zip(*(data[key] for key in (
        "frame_number", "timestamp_s", "channel", "name", "component", "value",
    ))):
        columns = ("x", "y", "z") if channel == "SEGMENT_ORIGINS" else ("w", "x", "y", "z")
        array = origins if channel == "SEGMENT_ORIGINS" else rotations
        array[slots[frame], names[name], columns.index(component)] = value
        if frame in timestamps:
            assert timestamps[frame] == timestamp
        timestamps[frame] = timestamp
    body_rows = [names[name] for name, _, _ in BODY_BINDINGS]
    valid = np.flatnonzero(np.isfinite(origins[:, body_rows]).all(axis=(1, 2)) &
                           np.isfinite(rotations[:, body_rows]).all(axis=(1, 2)))
    assert len(valid) > 0, "Reference contains no complete body pose for the declared VMC profile"
    selected = np.unique(valid[[0, len(valid) // 2, -1]])
    projector = VmcProjector(VmcConfig())
    conversion = np.array([[1., 0, 0], [0, 0, 1], [0, 1, 0]])
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
        receiver.bind(("127.0.0.1", 0))
        receiver.settimeout(2.)
        emitter = VmcEmitter(VmcConfig(port=receiver.getsockname()[1]))
        try:
            for slot in selected:
                number = frame_numbers[slot]
                timestamp_ns = timestamps[number] * 1e9  # Preserve stored source-time representation.
                channels = (
                    ChannelBlock(ChannelKind.SEGMENT_ORIGINS, ("x", "y", "z"), origins[slot].astype("<f4").tobytes()),
                    ChannelBlock(ChannelKind.ROTATIONS_WORLD, ("w", "x", "y", "z"), rotations[slot].astype("<f4").tobytes()),
                )
                frame = FrameMessage(envelope=MessageEnvelope(timestamp=timestamp_ns), frame_number=number,
                                     models=(model,), instances=(ModelInstance(0, model.model_id, channels),))
                sample = OutputSample(frame, "reference-replay", timestamp_ns)
                emitter.emit(sample)
                wire = receive_frame(receiver, 1200)
                assert wire[-2] == ("/VMC/Ext/OK", [1])
                pose = projector.project(frame, timestamp_ns)
                assert pose.source_timestamp_ns == timestamp_ns
                received = {values[0]: values[1:] for address, values in wire if address == "/VMC/Ext/Bone/Pos"}
                world_positions, world_rotations = {}, {}
                for row, (source_name, target_name, _) in enumerate(projector.bindings):
                    values = received[target_name]
                    parent = projector.parents[row]
                    parent_rotation = np.eye(3) if parent < 0 else world_rotations[int(parent)]
                    parent_position = pose.root_position_m if parent < 0 else world_positions[int(parent)]
                    world_rotations[row] = parent_rotation @ Rotation.from_quat(values[3:]).as_matrix()
                    world_positions[row] = parent_position + parent_rotation @ values[:3]
                    np.testing.assert_allclose(world_positions[row], conversion @ origins[slot, names[source_name]] / 1000., atol=2e-6)
        finally:
            emitter.close()
