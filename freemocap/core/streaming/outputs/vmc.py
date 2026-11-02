"""VMC output bindings for normalized VRM0 and the original reference rig.

This is a target binding, not another skeleton or pose solver. Source names and
world-rest frames come from the composed Forge model; target original rig frames
come from the reference glTF shipped beside Forge's authored rest_pose.yaml.
VRM0 receivers use normalized T-pose axes; the original reference rig remains an
explicit option. [@vmcProtocolSpecification; @evmc4uOriginalRigReceiver;
@vseeFacePreviewNormalizer; @vseeFacePreviewReceiver]
"""
from __future__ import annotations

import json
import math
import socket
import struct
from dataclasses import dataclass
from importlib.resources import files
from ipaddress import IPv4Address
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, IPvAnyAddress
from skellyforge.core.math.geometry.coordinate_systems import (
    CoordinateSystemRegistry, CoordinateSystemTransform,
)
from skellyforge.core.math.geometry.rotation_quaternion import (
    quaternions_to_rotation_matrices, rotation_matrices_to_quaternions,
)

from freemocap.core.streaming.message_model import (
    ChannelKind, CoordinateConvention, FrameMessage, ModelDefinition,
    STANDARD_HUMAN_MODEL_ID,
)

from freemocap.core.streaming.outputs.contracts import OutputSample  # noqa: TC001 — beartype resolves this at runtime


class VmcConfig(BaseModel):
    """Explicit receiver rest-axis binding; source geometry stays unchanged."""
    model_config = ConfigDict(extra="forbid", frozen=True)
    host: IPvAnyAddress = IPv4Address("127.0.0.1")
    port: int = Field(default=39539, ge=1, le=65535)
    model_id: str = Field(default=STANDARD_HUMAN_MODEL_ID, min_length=1)
    instance_id: int = Field(default=0, ge=0)
    profile: Literal["vrm0_normalized", "forge_reference_vrm_original"] = "vrm0_normalized"
    include_fingers: bool = True
    max_datagram_bytes: int = Field(default=1200, ge=256, le=1400)


# Target vocabulary only. Source hierarchy/rest geometry are never reproduced here.
# Entries: existing Forge segment, Unity HumanBodyBones name, reference asset node.
BODY_BINDINGS = (
    ("pelvis", "Hips", "hips"),
    ("sacrolumbar", "Spine", "spine"),
    ("thoracic", "Chest", "chest"),
    ("cervical_spine", "Neck", "neck"),
    ("skull", "Head", "head"),
) + tuple(
    (f"{side}_{source}", f"{side.title()}{target}", f"{node}.{suffix}")
    for side, suffix in (("left", "L"), ("right", "R"))
    for source, target, node in (
        ("clavicle", "Shoulder", "shoulder"),
        ("upper_arm", "UpperArm", "upper_arm"),
        ("lower_arm", "LowerArm", "lower_arm"),
        ("carpals", "Hand", "hand"),
        ("upper_leg", "UpperLeg", "upper_leg"),
        ("lower_leg", "LowerLeg", "lower_leg"),
        ("foot", "Foot", "foot"),
        ("toes", "Toes", "toes"),
    )
)
FINGER_BINDINGS = tuple(
    (f"{side}_{finger}_{source}", f"{side.title()}{target_finger}{target}",
     f"{node_finger}_{node}.{suffix}")
    for side, suffix in (("left", "L"), ("right", "R"))
    for finger, target_finger, node_finger in (
        ("thumb", "Thumb", "thumb"), ("index", "Index", "index"),
        ("middle", "Middle", "middle"), ("ring", "Ring", "ring"),
        ("pinky", "Little", "little"),
    )
    for source, target, node in (
        (("metacarpal" if finger == "thumb" else "proximal_phalanx"), "Proximal", "proximal"),
        (("proximal_phalanx" if finger == "thumb" else "middle_phalanx"), "Intermediate", "intermediate"),
        ("distal_phalanx", "Distal", "distal"),
    )
)


def _rotation_matrices(quaternions: np.ndarray) -> np.ndarray:
    if not np.isfinite(quaternions).all() or not np.allclose(
        np.linalg.norm(quaternions, axis=-1), 1., rtol=0., atol=1e-5,
    ):
        raise ValueError("VMC projection requires finite unit source quaternions")
    return quaternions_to_rotation_matrices(quaternions=quaternions)


def reference_rig() -> tuple[list[dict], np.ndarray, dict[int, int]]:
    """Read the original reference asset; no copied target rest constants."""
    path = files("skellyforge").joinpath("definitions/human_skeleton/default-vrm.gltf.json5")
    text = path.read_text(encoding="utf-8")
    # The authored reference is JSON with one leading provenance comment.
    document = json.loads(text[text.index("{"):])
    nodes = document["nodes"]
    parents: dict[int, int] = {}
    for parent, node in enumerate(nodes):
        for child in node.get("children", ()):
            if child in parents:
                raise ValueError("Reference avatar node has multiple parents")
            parents[child] = parent
    local = _rotation_matrices(np.asarray([
        [node.get("rotation", (0., 0., 0., 1.))[index] for index in (3, 0, 1, 2)]
        for node in nodes
    ], dtype=np.float64))
    world = np.empty_like(local)
    visited: set[int] = set()
    visiting: set[int] = set()

    def resolve(index: int) -> None:
        if index in visited:
            return
        if index in visiting:
            raise ValueError("Reference avatar hierarchy contains a cycle")
        visiting.add(index)
        if index in parents:
            resolve(parents[index])
            world[index] = world[parents[index]] @ local[index]
        else:
            world[index] = local[index]
        visiting.remove(index)
        visited.add(index)

    for index in range(len(nodes)):
        resolve(index)
    return nodes, world, parents


@dataclass(frozen=True)
class VmcPose:
    """Receiver coordinates; scientific source data and time remain untouched."""
    source_timestamp_ns: float | int
    bone_names: tuple[str, ...]
    root_position_m: np.ndarray
    local_positions_m: np.ndarray
    local_quaternions_xyzw: np.ndarray


class VmcProjector:
    def __init__(self, config: VmcConfig):
        self.config = config
        self.bindings = BODY_BINDINGS + (FINGER_BINDINGS if config.include_fingers else ())
        registry = CoordinateSystemRegistry.from_default_yaml()
        self.source_to_receiver = CoordinateSystemTransform(
            from_convention=registry.get(name="blender"),
            to_convention=registry.get(name="unity"),
        ).matrix
        asset_to_source = CoordinateSystemTransform(
            from_convention=registry.get(name="vrm"),
            to_convention=registry.get(name="blender"),
        ).matrix
        nodes, reference_world, reference_parents = reference_rig()
        node_indices = {node["name"]: index for index, node in enumerate(nodes)}
        selected = [node_indices[node] for _, _, node in self.bindings]
        target_rows = {node_index: row for row, node_index in enumerate(selected)}
        # All selected target nodes must have a selected immediate parent except
        # Hips, whose parent is the non-humanoid root controlled by Root/Pos.
        self.parents = np.asarray([
            -1 if row == 0 else target_rows[reference_parents[index]]
            for row, index in enumerate(selected)
        ])
        if config.profile == "vrm0_normalized":
            # VRM0 normalization freezes T-pose rotations into the mesh. Its
            # receiver bones have identity world/local rest rotations, not the
            # original Blender reference bone axes. [@vseeFacePreviewNormalizer]
            self.target_rest_world = np.broadcast_to(np.eye(3), (len(selected), 3, 3)).copy()
        else:
            self.target_rest_world = asset_to_source @ reference_world[selected] @ asset_to_source.T
        self.bone_names = tuple(target for _, target, _ in self.bindings)
        self._model: ModelDefinition | None = None

    def _bind(self, model: ModelDefinition) -> None:
        indices = {segment.name: index for index, segment in enumerate(model.segments)}
        required = tuple(source for source, _, _ in self.bindings)
        missing = {source for source, _, _ in BODY_BINDINGS} - indices.keys()
        if missing:
            raise ValueError(f"VMC profile requires existing human segments: {sorted(missing)}")
        # Finger metadata may be absent in body-only models. Mask those rows
        # before projection; the safe gather index is never emitted as a finger.
        self.source_present = np.asarray([name in indices for name in required])
        self.source_rows = np.asarray([indices.get(name, indices['pelvis']) for name in required])
        # RestSegment.rest_orientation is resolved WORLD rest, not the YAML's
        # parent-relative input. ModelDefinition.from_skeleton preserves this.
        source_rest = _rotation_matrices(np.asarray([
            model.segments[index].rest_orientation for index in self.source_rows
        ], dtype=np.float64))
        self.bind_rotation = source_rest.transpose(0, 2, 1) @ self.target_rest_world
        self._model = model

    def project(self, frame: FrameMessage, source_timestamp_ns: float | int) -> VmcPose | None:
        if not math.isfinite(source_timestamp_ns) or source_timestamp_ns < 0:
            raise ValueError("Invalid capture timestamp")
        if frame.convention != CoordinateConvention():
            raise ValueError("VMC profile requires the declared canonical millimeter/Blender quaternion stream")
        if frame.diagnostics is not None and frame.diagnostics.length_units != "millimeters":
            raise ValueError("VMC cannot project pixel-space reconstruction as measured metric poses")
        model = next((m for m in frame.models if m.model_id == self.config.model_id), None)
        instance = next((i for i in frame.instances if i.model_id == self.config.model_id
                         and i.instance_id == self.config.instance_id), None)
        if model is None or instance is None:
            return None
        if model is not self._model:
            if self._model is None or model.segments != self._model.segments:
                self._bind(model)
            else:
                self._model = model
        channels = {channel.kind: channel for channel in instance.channels if channel.camera_id is None}
        arrays = []
        valid = self.source_present.copy()
        for kind, columns in ((ChannelKind.SEGMENT_ORIGINS, ("x", "y", "z")),
                              (ChannelKind.ROTATIONS_WORLD, ("w", "x", "y", "z"))):
            channel = channels.get(kind)
            if channel is None:
                return None
            if channel.columns != columns:
                raise ValueError(f"Unexpected {kind} column order")
            values = np.frombuffer(channel.data, dtype="<f4")
            if values.size != len(model.segments) * len(columns):
                raise ValueError(f"Unexpected {kind} dimensions")
            if channel.sample_status is not None:
                status = np.frombuffer(channel.sample_status, dtype=np.uint8)
                if len(status) != len(model.segments):
                    raise ValueError("Unexpected VMC source status dimensions")
                valid &= status[self.source_rows] != 0
            arrays.append(values.reshape(-1, len(columns))[self.source_rows].astype(np.float64))
        origins, quaternions = arrays
        valid &= np.isfinite(origins).all(axis=1) & np.isfinite(quaternions).all(axis=1)
        # Root placement must be measured. A missing limb must not suppress the
        # valid torso/other limbs, but a local bone requires its valid ancestors.
        if not valid[0]:
            return None
        for row, parent in enumerate(self.parents):
            if parent >= 0:
                valid[row] &= valid[parent]
        source_world = _rotation_matrices(quaternions[valid])
        conversion = self.source_to_receiver
        target_world = np.full((len(valid), 3, 3), np.nan)
        target_world[valid] = conversion @ (source_world @ self.bind_rotation[valid]) @ conversion.T
        world_positions = origins @ conversion.T / 1000.
        root_position = world_positions[0].copy()
        parent_world = np.broadcast_to(np.eye(3), target_world.shape).copy()
        parent_positions = np.broadcast_to(root_position, world_positions.shape).copy()
        children = self.parents >= 0
        parent_world[children] = target_world[self.parents[children]]
        parent_positions[children] = world_positions[self.parents[children]]
        local_rotations = parent_world.transpose(0, 2, 1) @ target_world
        local_positions = np.einsum("nji,nj->ni", parent_world, world_positions - parent_positions)
        local_wxyz = rotation_matrices_to_quaternions(matrices=local_rotations[valid])
        names = tuple(name for name, keep in zip(self.bone_names, valid, strict=True) if keep)
        return VmcPose(source_timestamp_ns, names, root_position,
                       local_positions[valid], local_wxyz[:, (1, 2, 3, 0)])


def _osc_string(value: str) -> bytes:
    encoded = value.encode("utf-8") + b"\0"
    return encoded + b"\0" * (-len(encoded) % 4)


def osc_message(address: str, *values: str | int | float) -> bytes:
    tags, data = ",", bytearray()
    for value in values:
        if isinstance(value, str):
            tags += "s"
            data.extend(_osc_string(value))
        elif isinstance(value, int):
            tags += "i"
            data.extend(struct.pack(">i", value))
        else:
            tags += "f"
            data.extend(struct.pack(">f", value))
    return _osc_string(address) + _osc_string(tags) + bytes(data)


def osc_bundles(messages: list[bytes], limit: int) -> tuple[bytes, ...]:
    """Bound datagrams below configured MTU budget; OSC timetag 1 is immediate."""
    header = b"#bundle\0" + struct.pack(">Q", 1)
    current = bytearray(header)
    packets = []
    for message in messages:
        element = struct.pack(">I", len(message)) + message
        if len(header) + len(element) > limit:
            raise ValueError("VMC OSC message exceeds datagram budget")
        if len(current) + len(element) > limit:
            packets.append(bytes(current))
            current = bytearray(header)
        current.extend(element)
    if len(current) > len(header):
        packets.append(bytes(current))
    return tuple(packets)


class VmcEmitter:
    """Owned nonblocking UDP socket. Send success is not receiver acknowledgement."""
    def __init__(self, config: VmcConfig):
        self.config = config
        self.projector = VmcProjector(config)
        self.socket = socket.socket(socket.AF_INET6 if config.host.version == 6 else socket.AF_INET,
                                    socket.SOCK_DGRAM)
        self.socket.setblocking(False)
        self.destination = (str(config.host), config.port)
        self.closed = False
        self.first_timestamp_ns: float | int | None = None
        self.last_source_timestamp_ns: float | int | None = None
        self.invalid_samples = 0

    def emit(self, sample: OutputSample) -> None:
        if self.closed:
            raise RuntimeError("VMC output is closed")
        timestamp = sample.source_timestamp_ns
        pose = self.projector.project(sample.frame, timestamp)
        if self.first_timestamp_ns is None:
            self.first_timestamp_ns = timestamp
        if self.last_source_timestamp_ns is not None and timestamp < self.last_source_timestamp_ns:
            raise ValueError("VMC capture timestamps moved backwards")
        self.last_source_timestamp_ns = timestamp
        messages = []
        if pose is not None:
            messages.append(osc_message("/VMC/Ext/Root/Pos", "root",
                                        *map(float, pose.root_position_m), 0., 0., 0., 1.))
            for index, name in enumerate(pose.bone_names):
                messages.append(osc_message("/VMC/Ext/Bone/Pos", name,
                                            *map(float, pose.local_positions_m[index]),
                                            *map(float, pose.local_quaternions_xyzw[index])))
        else:
            self.invalid_samples += 1
        messages.append(osc_message("/VMC/Ext/OK", int(pose is not None)))
        # Represent elapsed measurement time, never the arrival/processing/send instant.
        messages.append(osc_message("/VMC/Ext/T", float(timestamp - self.first_timestamp_ns) / 1e9))
        for packet in osc_bundles(messages, self.config.max_datagram_bytes):
            sent = self.socket.sendto(packet, self.destination)
            if sent != len(packet):
                raise OSError("Incomplete VMC UDP datagram")

    def close(self) -> None:
        if not self.closed:
            self.closed = True
            self.socket.close()
