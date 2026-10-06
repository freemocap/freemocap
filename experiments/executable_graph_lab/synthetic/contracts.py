"""Versioned, validated boundary payloads; no production imports or live handles.

These cover the first adapter boundary. Numerical outputs remain fixture-only.
Dataclass fields drive both validation and exported inspector metadata.
"""
from dataclasses import dataclass, fields
import math
from typing import Literal, get_args, get_origin, get_type_hints


@dataclass(frozen=True)
class DetectorConfiguration:
    family: Literal['RTMPose']
    pose_model: str
    person_model: str
    requested_provider: Literal['CUDAExecutionProvider', 'CPUExecutionProvider']
    allow_cpu_fallback: bool


@dataclass(frozen=True)
class RecordingTiming:
    camera_ids: list[int]
    frame_numbers: list[int]
    timestamps_s: list[float]
    provenance: str


@dataclass(frozen=True)
class InferenceSession:
    session_id: str
    configuration: DetectorConfiguration
    camera_ids: list[int]
    actual_provider: Literal['simulated', 'CUDAExecutionProvider', 'CPUExecutionProvider']
    live_handle: Literal[False]


@dataclass(frozen=True)
class VideoFrame:
    frame: int
    camera: int
    timestamp: float
    synthetic_image: Literal[True]


@dataclass(frozen=True)
class EncodedFrameReceipt:
    frame: int
    camera: int
    encoded: Literal[True]
    stream_closed: bool
    publication: Literal['pending', 'simulated']
    durable: Literal[False]
    recording_id: str


@dataclass(frozen=True)
class PublicationPlan:
    recording_id: str
    task: Literal['mocap', 'pose', 'calibration']
    mode: Literal['simulated']
    durable: Literal[False]


@dataclass(frozen=True)
class PublicationReceipt:
    items: int
    synthetic: Literal[True]
    publication: Literal['simulated']
    durable: Literal[False]
    recording_id: str
    stage: str
    provenance: dict[str, list[str]]


CONTRACTS = dict(recording_timing=RecordingTiming, detector_configuration=DetectorConfiguration,
                 inference_session=InferenceSession, video_frame=VideoFrame,
                 encoded_frame_receipt=EncodedFrameReceipt, publication_plan=PublicationPlan,
                 publication_receipt=PublicationReceipt)


def check(value, kind, path):
    origin, args = get_origin(kind), get_args(kind)
    if origin is Literal:
        valid = any(type(value) is type(x) and value == x for x in args)
    elif origin is list:
        valid = isinstance(value, list)
        if valid:
            for i, item in enumerate(value): check(item, args[0], f'{path}[{i}]')
    elif origin is dict:
        valid = isinstance(value, dict)
        if valid:
            for key, item in value.items():
                check(key, args[0], path)
                check(item, args[1], f'{path}.{key}')
    elif hasattr(kind, '__dataclass_fields__'):
        hints = get_type_hints(kind)
        valid = isinstance(value, dict) and set(value) == set(hints)
        if valid:
            for name, field_type in hints.items(): check(value[name], field_type, f'{path}.{name}')
    elif kind is float:
        valid = type(value) in (float, int) and math.isfinite(value)
    else:
        valid = type(value) is kind and (kind is not str or bool(value.strip()))
    if not valid: raise ValueError(f'Invalid payload at {path}: expected {kind}')


def validate_payload(data_type, payload):
    if data_type not in CONTRACTS:
        return  # Explicitly marked fixture-only in exported metadata.
    check(payload, CONTRACTS[data_type], data_type)
    if data_type == 'recording_timing':
        cameras, frames, times = payload['camera_ids'], payload['frame_numbers'], payload['timestamps_s']
        if (not cameras or len(set(cameras)) != len(cameras) or min(cameras) < 0
                or not frames or frames != list(range(len(frames))) or len(times) != len(frames)
                or any(b <= a for a, b in zip(times, times[1:]))):
            raise ValueError('Invalid synchronized recording timing')
    if data_type == 'inference_session':
        cfg = payload['configuration']
        actual = payload['actual_provider']
        if actual != 'simulated' and actual != cfg['requested_provider'] and not cfg['allow_cpu_fallback']:
            raise ValueError('Execution provider violates fallback policy')
        if not payload['camera_ids'] or len(set(payload['camera_ids'])) != len(payload['camera_ids']):
            raise ValueError('Invalid inference session camera identities')
    for name in ('frame', 'camera', 'items'):
        if name in payload and payload[name] < 0: raise ValueError(f'Negative {name}')


def describe_contracts(types):
    return {name: dict(version=1, validation='boundary' if name in CONTRACTS else 'fixture-only',
                       fields={f.name: str(f.type) for f in fields(CONTRACTS[name])} if name in CONTRACTS else {})
            for name in sorted(types)}
