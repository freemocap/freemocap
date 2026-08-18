"""Contexts passed to channel producers.

StreamContext is the structural (composition-time) state: what the producers need to
declare activeness and a change signature — it never carries per-frame values.
FrameContext is the per-frame payload passed to fill().
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from freemocap.core.streaming.message_model import CalibratedCamera  # noqa: TC001
from skellyforge.skellymodels.standard_human.human_skeleton import HumanSkeleton  # noqa: TC002


@dataclass
class StreamContext:
    """Structural only, no per-frame data."""

    standard_human: HumanSkeleton
    camera_ids: tuple[str, ...] = ()
    calibrated_cameras: tuple[CalibratedCamera, ...] = ()
    tracker_keypoint_names: tuple[str, ...] = ()
    detector_type: str = "rtmpose"
    pipeline_live: bool = False


@dataclass
class FrameContext:
    """Per-frame payload passed to each active producer's fill()."""

    frame_number: int
    timestamp: float
    aggregator_output: Any | None = None  # duck-typed: the concrete type pulls skellytracker/mediapipe
    image_payload: bytes | None = None
    stream_context: StreamContext | None = None
