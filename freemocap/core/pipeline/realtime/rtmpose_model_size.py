"""Map UI realtime model size to skellytracker `RTMPoseDetectorConfig.mode`.

Skellytracker accepts ``\"performance\" | \"balanced\" | \"lightweight\"`` (see
``RTMPoseSessionConfig``). Default factory in this repo uses ``\"balanced\"``.

Mapping (verified against skellytracker defaults: ``mode='performance'`` is the
fastest preset in ``RTMPoseDetectorConfig``):

* **lite** → ``performance`` (fastest)
* **full** → ``balanced``
* **heavy** → ``lightweight`` (largest / most accurate)
"""

from __future__ import annotations

from typing import Literal

RealtimeModelSize = Literal["lite", "full", "heavy"]

RTMPOSE_MODE_BY_SIZE: dict[RealtimeModelSize, str] = {
    "lite": "performance",
    "full": "balanced",
    "heavy": "lightweight",
}


def rtmpose_mode_for_size(size: RealtimeModelSize) -> str:
    return RTMPOSE_MODE_BY_SIZE.get(size, "balanced")
