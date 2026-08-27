"""Which skeletons a run tracks, decided in ONE place.

Both the aggregator (which reconstructs them) and the websocket server (which describes
them on the wire) need this answer, and they must not be able to disagree: a frame whose
models and whose instances came from different opinions about what is being tracked is a
frame no client can reconcile.

So the decision is here, taken from the camera-node config that already says which trackers
are running.
"""
from __future__ import annotations

from freemocap.core.pipeline.realtime.camera_node_config import CameraNodeConfig
from freemocap.core.skeletons.charuco_board_skeleton import build_charuco_board_bundle
from freemocap.core.skeletons.standard_human_skeleton import build_standard_human_bundle
from freemocap.core.skeletons.tracked_skeleton_bundle import TrackedSkeletonBundle


def build_tracked_skeletons(
    *, camera_node_config: CameraNodeConfig, scale_window_frames: int
) -> tuple[TrackedSkeletonBundle, ...]:
    """Every skeleton this configuration tracks, in wire order.

    A skeleton is present exactly when its tracker is enabled — the config already says
    which detectors run, so nothing here re-decides it. Enabling charuco tracking is what
    makes the board a tracked object, not a separate switch.

    Args:
        camera_node_config: what the camera nodes are configured to detect.
        scale_window_frames: how many frames each skeleton's scale fit remembers. One
            number for all of them: they see the same cameras at the same framerate.
    """
    bundles: list[TrackedSkeletonBundle] = []
    if camera_node_config.skeleton_tracking_enabled:
        bundles.append(
            build_standard_human_bundle(
                detector_type=camera_node_config.detector_type,
                scale_window_frames=scale_window_frames,
            )
        )
    if camera_node_config.charuco_tracking_enabled:
        bundles.append(
            build_charuco_board_bundle(
                # The board the DETECTOR is configured with, so the model and the points
                # it is fitted from cannot describe different boards.
                board=camera_node_config.charuco_board,
                scale_window_frames=scale_window_frames,
            )
        )
    return tuple(bundles)
