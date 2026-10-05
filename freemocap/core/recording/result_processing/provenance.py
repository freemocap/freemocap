"""Record actual execution inputs without interpreting historical defaults."""

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from importlib import metadata
import json
from pathlib import Path
import platform
from uuid import uuid4

import numpy as np
from pydantic import BaseModel

from freemocap.core.pipeline.posthoc.processing_request import ProcessingStage
from freemocap.core.recording.data_descriptors.stage_provenance import StageProvenance
from freemocap.core.recording.result_processing.input_signatures import definition_signature, point_array_signature


def provenance_signature(value: object) -> str:
    """Hash domain serializers, including CameraModel's NumPy-backed geometry."""
    def encode(item):
        if isinstance(item, BaseModel):
            return encode(item.model_dump(mode="json"))
        if isinstance(item, np.ndarray):
            return dict(shape=list(item.shape), content=point_array_signature(item))
        if isinstance(item, dict):
            return {key: encode(child) for key, child in item.items()}
        if isinstance(item, (list, tuple)):
            return [encode(child) for child in item]
        return item
    return definition_signature(encode(value))


def software_identity() -> dict:
    """Include installed revisions and local core content (version alone can lag)."""
    packages = {}
    for name in ("freemocap", "skellyforge", "skellytracker", "skellycam", "numpy", "scipy", "pyarrow"):
        dist = metadata.distribution(name)
        origin = json.loads(dist.read_text("direct_url.json") or "{}")
        packages[name] = dict(version=dist.version, commit=origin.get("vcs_info", {}).get("commit_id"))
    root = Path(__file__).resolve().parents[3]
    digest = hashlib.sha256()
    for path in sorted((root / "core").rglob("*.py")):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return dict(python=platform.python_version(), packages=packages, core_sha256=digest.hexdigest())


@dataclass(frozen=True)
class ProvenanceContext:
    attempt_id: str
    recorded_at: datetime
    software: dict

    @classmethod
    def create(cls):
        return cls(attempt_id=uuid4().hex, recorded_at=datetime.now(timezone.utc), software=software_identity())

    def record(self, *, settings: dict, defaults: dict | None, inputs: dict,
               sources: tuple[str, ...], base_run_id: int | None = None,
               base_descriptor=None, limitations: tuple[str, ...] = ()) -> StageProvenance:
        return StageProvenance(attempt_id=self.attempt_id, recorded_at=self.recorded_at,
            effective_settings=settings, default_settings=defaults,
            input_signatures={key: provenance_signature(value) for key, value in inputs.items()},
            software=self.software, output_sources=tuple(dict.fromkeys(sources)),
            limitations=limitations,
            base_run_id=base_run_id,
            base_descriptor_signature=provenance_signature(base_descriptor) if base_descriptor is not None else None)


def stage_settings(stage: ProcessingStage, config: dict, *, filtering=None) -> dict:
    """Stage-owned options only; UI/export choices never become numerical settings."""
    if stage == ProcessingStage.OBSERVATIONS:
        return {key: config[key] for key in ("detector_type", "tracker_config", "charuco_tracking_enabled",
            "board_mode", "charuco_board") if key in config}
    if stage == ProcessingStage.TIMING:
        return {"video_fps": config["video_fps"]} if "video_fps" in config else {}
    if stage == ProcessingStage.TRIANGULATION:
        return {key: config[key] for key in ("triangulation_config", "camera_matching", "body_alignment") if key in config}
    if stage == ProcessingStage.FILTERING:
        return filtering.config.model_dump(mode="json") if filtering is not None else dict(config.get("filter_config", {}))
    if stage == ProcessingStage.SCALE_FIT:
        return dict(policy="recording_global_measured_support")
    if stage == ProcessingStage.RECONSTRUCTION:
        return dict(policy="saved_model_and_frozen_scale_fresh_roll_state")
    if stage == ProcessingStage.BIOMECHANICS:
        return dict(compute_center_of_mass=True)
    raise ValueError(f"Stage has its own settings adapter: {stage}")

