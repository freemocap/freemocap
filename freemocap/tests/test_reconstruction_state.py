"""What separating the bundle from its reconstruction state actually buys.

Three properties, each one a thing the posthoc pipeline depends on:

1. A bundle is immutable, so it can be shared between takes and pipelines.
2. Reconstruction is a pure function of (bundle, state, frame) — the same bundle with two
   fresh states gives the same answer, so nothing leaks between takes.
3. Posthoc's "global scale fit" and realtime's rolling one are literally the same object
   with a different window, so there is no second implementation to keep in step.
"""
from __future__ import annotations

import dataclasses

import numpy as np
import pytest
from skellyforge.core.math.geometry.spatial_vectors import Point
from skellyforge.core.skeleton.pose.hydration import hydrate_skeleton
from skellyforge.core.skeleton.pose.model_scale_fitting import (
    fit_model_scale,
    scale_voting_segment_names,
)
from skellyforge.core.skeleton.skeleton_pose import SkeletonPose

from freemocap.core.skeletons.reconstruct_skeleton import reconstruct_skeleton
from freemocap.core.skeletons.reconstruction_state import (
    FrozenModelScale,
    build_reconstruction_states,
    streaming_model_scale_source,
)
from freemocap.core.skeletons.standard_human_skeleton import build_standard_human_bundle
from freemocap.core.skeletons.tracked_skeleton_bundle import TrackedSkeletonBundle
from freemocap.tests.test_model_scale_in_the_loop import _standing_keypoints

WINDOW_FRAMES = 30


@pytest.fixture
def human_bundle() -> TrackedSkeletonBundle:
    return build_standard_human_bundle(detector_type="rtmpose")


def _fresh_state(bundle: TrackedSkeletonBundle, *, window_frames: int = WINDOW_FRAMES):
    return build_reconstruction_states(
        bundles=(bundle,),
        scale_source_for=streaming_model_scale_source(window_frames=window_frames),
    )[bundle.model_id]


def _hydrated_pose(bundle: TrackedSkeletonBundle) -> SkeletonPose:
    """One real pose, for tests that need to hand a scale source something valid."""
    mapped = bundle.landmark_mapping.apply(tracker_positions=_standing_keypoints())
    return hydrate_skeleton(
        skeleton=bundle.skeleton,
        observed={
            name: Point.from_array(values=position) for name, position in mapped.items()
        },
        require_all=False,
    )


def test_a_bundle_carries_no_mutable_reconstruction_state(
    human_bundle: TrackedSkeletonBundle,
) -> None:
    """The bundle says what a skeleton IS. Nothing that accumulates may live on it.

    It was `frozen=True` before this split and still held a scale fitter and a roll
    resolver, so "frozen" was a claim about the reference rather than about the object.
    """
    assert dataclasses.is_dataclass(human_bundle)
    with pytest.raises(dataclasses.FrozenInstanceError):
        human_bundle.model_id = "something-else"  # type: ignore[misc]

    field_names = {field.name for field in dataclasses.fields(human_bundle)}
    assert "scale_fitter" not in field_names
    assert "roll_resolver" not in field_names
    assert not hasattr(human_bundle, "reset")


def test_the_same_bundle_with_two_fresh_states_reconstructs_identically(
    human_bundle: TrackedSkeletonBundle,
) -> None:
    """The property the whole extraction exists for.

    If a bundle carried state, running a second take with it would inherit the first
    take's scale readings and roll carry. Reusing one bundle across takes has to be safe,
    because both pipelines do exactly that.
    """
    keypoints = _standing_keypoints()

    first = reconstruct_skeleton(
        bundle=human_bundle,
        state=_fresh_state(human_bundle),
        filtered_keypoints=keypoints,
        compute_center_of_mass=True,
    )
    second = reconstruct_skeleton(
        bundle=human_bundle,
        state=_fresh_state(human_bundle),
        filtered_keypoints=keypoints,
        compute_center_of_mass=True,
    )

    assert first is not None and second is not None
    assert first.fitted_scale_mm == second.fitted_scale_mm
    assert first.segment_lengths.keys() == second.segment_lengths.keys()
    for name, length in first.segment_lengths.items():
        assert length == second.segment_lengths[name]
    for name, rotation in first.segment_rotations_world.items():
        np.testing.assert_array_equal(rotation, second.segment_rotations_world[name])
    np.testing.assert_array_equal(first.center_of_mass, second.center_of_mass)


def test_a_reused_state_accumulates_where_a_fresh_one_does_not(
    human_bundle: TrackedSkeletonBundle,
) -> None:
    """The other half: state is what remembers, and it is supposed to."""
    state = _fresh_state(human_bundle)
    keypoints = _standing_keypoints()

    assert not state.scale_source.has_model_scale
    reconstruct_skeleton(
        bundle=human_bundle,
        state=state,
        filtered_keypoints=keypoints,
        compute_center_of_mass=False,
    )
    assert state.scale_source.has_model_scale

    state.reset()
    assert not state.scale_source.has_model_scale


def test_the_global_fit_is_the_streaming_fitter_with_a_whole_recording_window(
    human_bundle: TrackedSkeletonBundle,
) -> None:
    """Posthoc's whole-take scale fit needs no new code — it is a bigger window.

    `StreamingModelScaleFitter.current_fit()` calls `fit_model_scale` over its window. Give
    it the recording's frame count and the ring never wraps, so the window IS every sample
    the recording produced. Pinning this equivalence is what stops a second "batch fitter"
    implementation being written later and drifting from this one.
    """
    frame_count = 8
    voting = scale_voting_segment_names(
        skeleton=human_bundle.skeleton,
        measured_landmark_names=human_bundle.landmark_mapping.directly_measured_landmark_names,
    )

    state = _fresh_state(human_bundle, window_frames=frame_count)
    for _ in range(frame_count):
        reconstruct_skeleton(
            bundle=human_bundle,
            state=state,
            filtered_keypoints=_standing_keypoints(),
            compute_center_of_mass=False,
        )

    streamed_fit = state.scale_source.current_fit()
    batch_fit = fit_model_scale(
        skeleton=human_bundle.skeleton,
        # The windows the fitter accumulated ARE the samples a batch call is handed.
        scale_samples=state.scale_source._windows,  # noqa: SLF001 — pinning an equivalence
        voting_segment_names=voting,
    )

    assert streamed_fit.fitted_scale == batch_fit.fitted_scale
    assert streamed_fit.segment_lengths == batch_fit.segment_lengths


def test_a_frozen_scale_offers_one_fit_to_every_frame(
    human_bundle: TrackedSkeletonBundle,
) -> None:
    """The posthoc pass-two scale source: measured once, never moved by a later frame."""
    state = _fresh_state(human_bundle)
    reconstruct_skeleton(
        bundle=human_bundle,
        state=state,
        filtered_keypoints=_standing_keypoints(),
        compute_center_of_mass=False,
    )
    measured = state.scale_source.current_fit()

    frozen = FrozenModelScale(fit=measured)
    assert frozen.has_model_scale
    assert frozen.current_fit() is measured
    # Inert rather than raising: the posthoc driver runs the identical reconstruction loop,
    # and having it branch on which scale source it holds is the duplication to avoid.
    frozen.observe_pose(pose=_hydrated_pose(human_bundle))
    assert frozen.current_fit() is measured
