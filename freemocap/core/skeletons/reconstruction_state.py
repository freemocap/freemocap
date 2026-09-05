"""What reconstructing one skeleton remembers between frames.

`TrackedSkeletonBundle` says WHAT is being reconstructed — a definition, a rest pose, a
mapping, a mass model. It is authored once and identical for every run that tracks the same
thing. This module holds the other half: the things that accumulate as frames go by, and
which therefore belong to a single take rather than to the skeleton.

Keeping them apart is what lets ONE `reconstruct_skeleton` serve both pipelines. Realtime
threads a live streaming state through it; posthoc threads a state whose scale was fitted
over the whole recording. Neither pipeline has its own copy of the math, because the only
thing that differed was where the memory lived.

This mirrors skellytracker, where `Tracker` is documented "stateless between calls" and
`TrackerState` is passed in and out. Same reason, same shape.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable  # noqa: TC003 - runtime type checking
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np
from skellyforge.core.skeleton.pose.model_scale_fitting import (
    ModelScaleFit,
    InsufficientScaleEvidence,
    StreamingModelScaleFitter,
    scale_voting_segment_names,
)
from skellyforge.core.skeleton.pose.roll_resolution import ContinuousRollResolver
from skellyforge.core.skeleton.skeleton_pose import SkeletonPose  # noqa: TC002 - runtime type checking

from freemocap.core.skeletons.tracked_skeleton_bundle import TrackedSkeletonBundle  # noqa: TC001 - runtime type checking


@runtime_checkable
class ModelScaleSource(Protocol):
    """How a frame learns how big the skeleton it is reconstructing is.

    A Protocol because the two answers differ only in WHEN the fit is decided, and the
    reconstruction has no reason to know which it was handed. Streaming re-fits from a
    rolling window as evidence arrives; posthoc measures once over the whole take and
    offers that same fit to every frame of it.
    """

    def observe_pose(self, *, pose: SkeletonPose) -> None:
        """Record this frame's reading of how big the model is."""
        ...

    @property
    def has_model_scale(self) -> bool:
        """Whether anything entitled to vote has been seen yet.

        Ask before `current_fit`. Answering "not yet" is not the same as being handed a
        plausible default.
        """
        ...

    def current_fit(self) -> ModelScaleFit:
        """The fit over everything observed so far."""
        ...


@dataclass(frozen=True, slots=True)
class FrozenModelScale:
    """One fit, measured once over a whole recording, offered to every frame of it.

    The posthoc counterpart of `StreamingModelScaleFitter`: a take has ONE subject of ONE
    size, so once the whole recording has been seen there is nothing left for a later frame
    to teach. `observe_pose` is deliberately inert rather than raising — the caller runs the
    identical reconstruction loop, and having it branch on which scale source it holds is
    exactly the duplication this design exists to avoid.
    """

    fit: ModelScaleFit | None

    def observe_pose(self, *, pose: SkeletonPose) -> None:
        return None

    @property
    def has_model_scale(self) -> bool:
        return self.fit is not None

    def current_fit(self) -> ModelScaleFit:
        if self.fit is None:
            raise InsufficientScaleEvidence("The recording contains no scale evidence")
        return self.fit


@dataclass(slots=True)
class SkeletonReconstructionState:
    """Everything reconstructing ONE skeleton carries from frame to frame.

    Mutable by necessity and per-take by construction. Held BESIDE its bundle, never
    inside it, so a bundle stays genuinely frozen and shareable while the state stays with
    the take its measurements were taken in.

    Attributes:
        model_id: the bundle this state belongs to. Present so a caller holding both
            keyed by model cannot pair them up wrongly.
        scale_source: how this take learns the skeleton's size.
        roll_resolver: carries roll continuity for segments that cannot measure their own.
            `None` for a skeleton that measures its roll — a rigid marked object does, and
            applying a continuity convention to it would invent state where there is a
            measurement.
        previous_center_of_mass: the last centre of mass and the time it was placed, for
            the streaming velocity estimate that extrapolated centre of mass needs. Batch
            drivers leave this `None` and take velocity from the whole trajectory instead.
    """

    model_id: str
    scale_source: ModelScaleSource
    roll_resolver: ContinuousRollResolver | None = None
    previous_center_of_mass: tuple[np.ndarray, float] | None = None

    def reset(self) -> None:
        """Forget everything measured so far.

        Called when the body being tracked may have changed (the skeleton-fit reset
        signal) or when the frame those measurements were taken in has (a calibration
        hot-reload).
        """
        if isinstance(self.scale_source, StreamingModelScaleFitter):
            self.scale_source.reset()
        if self.roll_resolver is not None:
            self.roll_resolver.reset()
        self.previous_center_of_mass = None


def streaming_model_scale_source(
    *, window_frames: int
) -> Callable[[TrackedSkeletonBundle], ModelScaleSource]:
    """A scale source that re-fits from a rolling window of the last `window_frames`.

    Pass the recording's frame count to get the whole-take fit: the window never wraps, so
    `current_fit()` is `fit_model_scale` over every sample. Posthoc's "global fit" and
    realtime's rolling one are the same object with a different number — there is no second
    implementation to keep in step.
    """

    def build(bundle: TrackedSkeletonBundle) -> ModelScaleSource:
        return StreamingModelScaleFitter(
            skeleton=bundle.skeleton,
            # Only landmarks the mapping MEASURES may set the fitted scale. Constructed
            # landmarks are near noise-free, so a consistency-weighted estimator would
            # otherwise rank the template as its own best evidence.
            voting_segment_names=scale_voting_segment_names(
                skeleton=bundle.skeleton,
                measured_landmark_names=bundle.landmark_mapping.directly_measured_landmark_names,
            ),
            window_frames=window_frames,
        )

    return build


def build_reconstruction_states(
    *,
    bundles: Iterable[TrackedSkeletonBundle],
    scale_source_for: Callable[[TrackedSkeletonBundle], ModelScaleSource],
) -> dict[str, SkeletonReconstructionState]:
    """One fresh state per bundle, keyed by model id.

    The roll resolver is derived from the skeleton rather than passed in: a skeleton
    declares whether it needs roll resolved (`roll_resolution` in its derived quantities),
    so nothing here decides it per skeleton type. A board gets `None` because its
    definition declares no derived quantities, not because this function knows it is a
    board.
    """
    return {
        bundle.model_id: SkeletonReconstructionState(
            model_id=bundle.model_id,
            scale_source=scale_source_for(bundle),
            roll_resolver=(
                ContinuousRollResolver.for_skeleton(
                    skeleton=bundle.skeleton,
                    rest_relative_orientations=bundle.rest_pose.relative_orientations,
                )
                if "roll_resolution" in bundle.skeleton.derived_quantities
                else None
            ),
        )
        for bundle in bundles
    }
