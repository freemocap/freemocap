"""Deterministic, lazy Cartesian test plans; unexecuted cases never imply coverage."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
from itertools import combinations, product
import json
from math import prod
from pathlib import Path
from typing import Iterator


def camera_subsets(camera_ids: tuple[str, ...]) -> tuple[tuple[str, ...], ...]:
    if len(set(camera_ids)) != len(camera_ids) or not camera_ids:
        raise ValueError('Camera inventory must contain distinct identities')
    return tuple(selection for size in range(len(camera_ids) + 1)
                 for selection in combinations(sorted(camera_ids), size))


@dataclass(frozen=True)
class HardwareCase:
    case_kind: str
    capture_backend: str
    initial_cameras: tuple[str, ...]
    requested_cameras: tuple[str, ...]
    initial_state: str
    destination_backend: str
    camera_settings: dict = field(default_factory=dict)

    @property
    def case_id(self) -> str:
        serialized = json.dumps(asdict(self), sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(serialized.encode()).hexdigest()[:20]

    def to_record(self) -> dict:
        return {'case_id': self.case_id, **asdict(self)}


@dataclass(frozen=True)
class MatrixPlan:
    camera_ids: tuple[str, ...]
    capture_backends: tuple[str, ...] = ('python', 'rust')
    capture_states: tuple[str, ...] = ('streaming', 'paused', 'recording')
    # These are declared test levels, not a claim to enumerate continuous numbers.
    setting_axes: dict = field(default_factory=lambda: {
        'resolution': [{'width': 640, 'height': 480}, {'width': 1280, 'height': 720}, {'width': 1920, 'height': 1080}],
        'rotation': [-1, 0, 1, 2],
        'exposure_mode': ['MANUAL', 'AUTO', 'RECOMMEND'],
        'exposure': list(range(-13, -3)),
        'framerate': [-1.0, 0.0, 30.0],
        'capture_fourcc': ['MJPG', 'X264', 'YUYV', 'H264'],
        'writer_fourcc': ['MJPG', 'X264', 'YUYV', 'H264'],
        'pixel_format': ['RGB', 'BGR', 'GRAY'],
        'color_channels': [1, 3, 4],
    })

    def __post_init__(self):
        camera_subsets(self.camera_ids)
        if not self.capture_backends or not set(self.capture_backends) <= {'python', 'rust'}:
            raise ValueError('Capture backends must be python and/or rust')
        if not self.setting_axes or any(not values for values in self.setting_axes.values()):
            raise ValueError('Every settings axis must contain test levels')

    def transition_cases(self) -> Iterator[HardwareCase]:
        selections = camera_subsets(self.camera_ids)
        for backend, destination, initial, requested, state in product(
                self.capture_backends, self.capture_backends, selections, selections, self.capture_states):
            yield HardwareCase('camera_transition', backend, initial, requested, state, destination)

    def settings_cases(self) -> Iterator[HardwareCase]:
        names = tuple(self.setting_axes)
        for backend, selected, state in product(self.capture_backends, camera_subsets(self.camera_ids)[1:], self.capture_states):
            for targeted in camera_subsets(selected)[1:]:
                for values in product(*(self.setting_axes[name] for name in names)):
                    yield HardwareCase('camera_settings', backend, selected, targeted, state, backend, dict(zip(names, values)))

    def counts(self) -> dict[str, int]:
        camera_count = len(self.camera_ids)
        return {
            'camera_transition': len(self.capture_backends) ** 2 * 4 ** camera_count * len(self.capture_states),
            # Each identity is absent, present-but-untargeted, or targeted; exclude no-target cases.
            'camera_settings': len(self.capture_backends) * (3 ** camera_count - 2 ** camera_count)
                * len(self.capture_states) * prod(len(values) for values in self.setting_axes.values()),
        }

    def write_manifest(self, output_path: Path) -> None:
        output_path.write_text(json.dumps({'schema_version': 1, **asdict(self),
            'case_counts': self.counts(), 'case_status': 'not_run',
            'scope': 'Full Cartesian product of declared levels; each targeted subset receives the declared settings.',
        }, indent=2), encoding='utf-8')
