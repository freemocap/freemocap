"""Which skeletons a run tracks, decided in ONE place.

Both the aggregator (which reconstructs them) and the websocket server (which describes
them on the wire) need this answer, and they must not be able to disagree: a frame whose
models and whose instances came from different opinions about what is being tracked is a
frame no client can reconcile.

So the decision is here, taken from the camera-node config that already says which trackers
are running.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from freemocap.core.pipeline.realtime.camera_node_config import CameraNodeConfig
from freemocap.core.skeletons.charuco_board_skeleton import build_charuco_board_bundle
from freemocap.core.skeletons.reconstruction_state import (
    ModelScaleSource,
    SkeletonReconstructionState,
    build_reconstruction_states,
)
from freemocap.core.skeletons.standard_human_skeleton import build_standard_human_bundle
from freemocap.core.skeletons.tracked_skeleton_bundle import TrackedSkeletonBundle


def build_tracked_skeletons(
    *, camera_node_config: CameraNodeConfig
) -> tuple[TrackedSkeletonBundle, ...]:
    """Every skeleton this configuration tracks, in wire order.

    A skeleton is present exactly when its tracker is enabled — the config already says
    which detectors run, so nothing here re-decides it. Enabling charuco tracking is what
    makes the board a tracked object, not a separate switch.

    Args:
        camera_node_config: what the camera nodes are configured to detect.
    """
    bundles: list[TrackedSkeletonBundle] = []
    if camera_node_config.skeleton_tracking_enabled:
        bundles.append(
            build_standard_human_bundle(
                detector_type=camera_node_config.detector_type,
            )
        )
    if camera_node_config.charuco_tracking_enabled:
        bundles.append(
            build_charuco_board_bundle(
                # The board the DETECTOR is configured with, so the model and the points
                # it is fitted from cannot describe different boards.
                board=camera_node_config.charuco_board,
            )
        )
    return tuple(bundles)


@dataclass(frozen=True, slots=True)
class TrackedSkeletonSet:
    """The skeletons a run reconstructs, paired with what reconstructing them remembers.

    Bundles and states are handed out together because they must be rebuilt together. A
    detector change rebuilds the bundles — a different detector measures different
    landmarks — and the readings taken through the old mapping must not carry over into the
    new one. Returning them as one value makes "rebuild one but not the other" impossible
    to express, which is how that leak got in.
    """

    bundles: tuple[TrackedSkeletonBundle, ...]
    states: dict[str, SkeletonReconstructionState]

    def state_for(self, bundle: TrackedSkeletonBundle) -> SkeletonReconstructionState:
        return self.states[bundle.model_id]

    def reset(self) -> None:
        """Forget everything measured so far, for every skeleton.

        Called when the body being tracked may have changed (the skeleton-fit reset signal)
        or when the frame those measurements were taken in has (a calibration hot-reload).
        """
        for state in self.states.values():
            state.reset()


def build_tracked_skeleton_set(
    *,
    camera_node_config: CameraNodeConfig,
    scale_source_for: Callable[[TrackedSkeletonBundle], ModelScaleSource],
) -> TrackedSkeletonSet:
    """Every skeleton this configuration tracks, with a fresh state for each.

    Args:
        camera_node_config: what the camera nodes are configured to detect.
        scale_source_for: how each skeleton learns its size — a rolling window for a live
            stream, a whole-recording fit for a batch one. The only thing the two pipelines
            change about reconstruction.
    """
    bundles = build_tracked_skeletons(camera_node_config=camera_node_config)
    return TrackedSkeletonSet(
        bundles=bundles,
        states=build_reconstruction_states(
            bundles=bundles, scale_source_for=scale_source_for
        ),
    )
