"""The frame-emit path must not rebuild the data model.

`WebsocketServer._ensure_composition` runs on EVERY emitted frame. Building a skeleton set
loads the skeleton, rest-pose, mapping, centre-of-mass and anthropometry YAMLs off disk and
constructs 61 segments plus 124 landmarks — ~100ms. Doing that per frame caps the rate
frames reach the client at ~10fps while leaving the camera framerate untouched, so it looks
like a rendering problem rather than a server one. These tests pin the cost down.
"""
import time

import pytest

from freemocap.api.websocket.websocket_server import WebsocketServer
from freemocap.core.pipeline.realtime.camera_node import CameraNodeConfig
from freemocap.core.skeletons.tracked_skeleton_set import build_tracked_skeletons

SCALE_WINDOW_FRAMES = 30
# Generous: the memoized path measures ~0.01ms, the unmemoized one ~99ms. Anything near the
# latter fails, anything near the former passes, and drift in between is still caught.
MAX_MEAN_MS_PER_CALL = 1.0


class _MemoProbe:
    """Exercises the memo alone, without standing up a FastAPI app."""

    _tracked_skeletons_cache = None
    _skeletons_for = WebsocketServer._skeletons_for


@pytest.fixture
def probe() -> _MemoProbe:
    return _MemoProbe()


def test_the_skeleton_set_is_built_once_not_once_per_frame(probe: _MemoProbe) -> None:
    config = CameraNodeConfig()
    first = probe._skeletons_for(
        camera_node_config=config
    )

    call_count = 200
    start = time.perf_counter()
    for _ in range(call_count):
        repeated = probe._skeletons_for(
            camera_node_config=config
        )
    mean_ms = (time.perf_counter() - start) / call_count * 1000

    assert repeated is first, "an unchanged config must return the very same skeleton set"
    assert mean_ms < MAX_MEAN_MS_PER_CALL, (
        f"the frame-emit path rebuilt the data model: {mean_ms:.1f}ms per call. "
        "Something on the per-frame path is constructing skeletons again."
    )


def test_a_changed_board_still_rebuilds(probe: _MemoProbe) -> None:
    """The memo must not serve a stale model when the config genuinely changes."""
    default_board = CameraNodeConfig()
    legacy_board = CameraNodeConfig()
    legacy_board.charuco_board.squares_x = 7
    legacy_board.charuco_board.squares_y = 5

    default_skeletons = probe._skeletons_for(
        camera_node_config=default_board
    )
    legacy_skeletons = probe._skeletons_for(
        camera_node_config=legacy_board
    )

    assert legacy_skeletons is not default_skeletons


def test_building_a_skeleton_set_is_expensive_enough_to_be_worth_memoizing() -> None:
    """Documents WHY the memo exists, and fails if the cost ever quietly moves.

    If this ever gets cheap, the memo can go — but nobody should have to rediscover the
    cost by watching their framerate collapse.
    """
    config = CameraNodeConfig()
    build_tracked_skeletons(
        camera_node_config=config
    )  # warm import-time caches

    start = time.perf_counter()
    build_tracked_skeletons(
        camera_node_config=config
    )
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert elapsed_ms > MAX_MEAN_MS_PER_CALL, (
        f"building a skeleton set now costs {elapsed_ms:.2f}ms — if that is genuinely "
        "cheap now, revisit the memo in WebsocketServer._skeletons_for."
    )


def test_the_frame_emit_path_does_not_stat_the_calibration_file() -> None:
    """The websocket server must not poll calibration from the frame-emit path.

    It used to hold its OWN `CalibrationStateTracker` and call `check_for_update()` from
    `_ensure_composition` — an `os.path.getmtime` syscall on every emitted frame, plus a
    second, independent opinion about whether the calibration was valid. That second
    opinion is why one process could invalidate a calibration while this one went on
    logging about it forever. Calibration now has exactly one owner (the aggregation
    node); this server only forwards the binding it publishes.
    """
    import inspect

    source = inspect.getsource(WebsocketServer)
    assert "CalibrationStateTracker" not in source, (
        "the websocket server must not own calibration state — the aggregation node is "
        "the single owner and publishes the binding on its output message"
    )
    assert "check_for_update" not in source, (
        "calibration file polling must not happen on the frame-emit path"
    )
