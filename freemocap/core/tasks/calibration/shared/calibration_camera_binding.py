"""Bind a loaded calibration's cameras to the cameras that are actually live.

A calibration is a set of `CameraModel`s recorded at some point in the past. The
cameras plugged in right now are a different set. Deciding which calibration camera
describes which live camera is *one* question with *one* answer, and this module is
where that answer is computed.

Two rules shape it:

- **camera_id is identity.** Ids are opaque; nothing here parses them. The only other
  signal considered is the *structured* integer index that both sides already carry
  (`CameraModel.index`, `CameraConfig.camera_index`) — never digits scraped out of a
  name. (`current-work-plans/00-foundation/conventions.md`: "structure travels in the
  model, never in string patterns".)
- **All or nothing.** A partial binding is not a binding. Handing one camera another
  camera's intrinsics produces a confidently wrong reconstruction, which is strictly
  worse than no reconstruction. If every live camera cannot be bound to a *distinct*
  calibration camera, the calibration simply does not apply to this camera set.

A calibration that does not apply is a normal, expected condition — cameras get
replugged and re-enumerated. Callers report it once and run 2D-only; they do not treat
it as an error and must not discard the calibration, which may fit again later.

Pure: no logging, no I/O, no clock. That is what lets the caller warn exactly once, and
what leaves room for the scored permutation search that will eventually replace the
index pass.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum

from skellycam.core.types.type_overloads import CameraIdString, CameraIndexInt

from freemocap.core.tasks.calibration.shared.camera_model import CameraModel


class CalibrationMatchKind(str, Enum):
    """How the live cameras were bound to the calibration's cameras."""

    EXACT = "exact"
    """Every live camera matched a calibration camera by id. The trustworthy case."""

    INDEX = "index"
    """No id match, but every live camera bound to a distinct calibration camera by
    structured index. Tolerable only because it is total and injective — the physical
    camera behind an index can still have changed, so callers say so out loud."""

    UNMATCHED = "unmatched"
    """The calibration does not describe this camera set. Not an error."""


@dataclass(frozen=True, slots=True)
class CalibrationBinding:
    """The resolved (or refused) mapping from live cameras to calibration cameras."""

    by_live_id: Mapping[CameraIdString, CameraModel | None]
    """EVERY live camera, always — the value is None when nothing was bound to it.
    Callers iterate this to describe the full live camera set, not a filtered subset."""

    kind: CalibrationMatchKind

    applicable: bool
    """True only when every live camera bound to a distinct calibration camera."""

    reason: str
    """One human sentence, suitable for the caller's single warning."""

    live_camera_ids: tuple[CameraIdString, ...]
    calibration_camera_ids: tuple[str, ...]

    @property
    def live_id_for_calibration_id(self) -> Mapping[str, CameraIdString]:
        """Inverse lookup, for surfaces keyed by calibration id that must report live ids."""
        return {
            model.id: live_id
            for live_id, model in self.by_live_id.items()
            if model is not None
        }


def _unmatched_binding(
    *,
    live_camera_ids: tuple[CameraIdString, ...],
    calibration_camera_ids: tuple[str, ...],
    reason: str,
) -> CalibrationBinding:
    return CalibrationBinding(
        by_live_id={live_id: None for live_id in live_camera_ids},
        kind=CalibrationMatchKind.UNMATCHED,
        applicable=False,
        reason=reason,
        live_camera_ids=live_camera_ids,
        calibration_camera_ids=calibration_camera_ids,
    )


def _id_sets_sentence(
    live_camera_ids: tuple[CameraIdString, ...],
    calibration_camera_ids: tuple[str, ...],
) -> str:
    return f"Live: {list(live_camera_ids)}; calibration: {list(calibration_camera_ids)}."


def bind_calibration_to_live_cameras(
    *,
    calibration_cameras: Sequence[CameraModel],
    live_camera_indices: Mapping[CameraIdString, CameraIndexInt],
) -> CalibrationBinding:
    """Decide which calibration camera (if any) describes each live camera.

    Args:
        calibration_cameras: the cameras the loaded calibration describes.
        live_camera_indices: every live camera id -> its structured `camera_index`.
            Taking the index map rather than the full `CameraConfigs` keeps this
            function free of capture-layer types and trivially testable.

    Returns:
        A `CalibrationBinding` covering every live camera. `applicable` is True only for
        a total, injective binding.
    """
    live_camera_ids = tuple(live_camera_indices.keys())
    calibration_camera_ids = tuple(camera.id for camera in calibration_cameras)
    id_sets = _id_sets_sentence(live_camera_ids, calibration_camera_ids)

    if not live_camera_ids:
        return _unmatched_binding(
            live_camera_ids=(),
            calibration_camera_ids=calibration_camera_ids,
            reason="No live cameras to bind a calibration to.",
        )
    if not calibration_cameras:
        return _unmatched_binding(
            live_camera_ids=live_camera_ids,
            calibration_camera_ids=(),
            reason="The loaded calibration describes no cameras.",
        )

    calibration_by_id: dict[str, CameraModel] = {cam.id: cam for cam in calibration_cameras}

    # ── Pass 1: exact id ──────────────────────────────────────────────────────────
    # A live set that is a subset of the calibration is fine — the extra calibration
    # cameras simply go unused (the sub-triangulator cache already handles that).
    if all(live_id in calibration_by_id for live_id in live_camera_ids):
        return CalibrationBinding(
            by_live_id={live_id: calibration_by_id[live_id] for live_id in live_camera_ids},
            kind=CalibrationMatchKind.EXACT,
            applicable=True,
            reason="Every live camera matched a calibration camera by id.",
            live_camera_ids=live_camera_ids,
            calibration_camera_ids=calibration_camera_ids,
        )

    # ── Pass 2: structured index ──────────────────────────────────────────────────
    # Rejected outright unless total AND injective AND free of the id-overlap case
    # below. A partial index binding is what silently pairs one camera's images with
    # another camera's intrinsics.
    calibration_by_index: dict[CameraIndexInt, CameraModel] = {}
    for camera in calibration_cameras:
        if camera.index in calibration_by_index:
            return _unmatched_binding(
                live_camera_ids=live_camera_ids,
                calibration_camera_ids=calibration_camera_ids,
                reason=(
                    f"No live camera id matched the calibration, and the calibration reuses "
                    f"index {camera.index} for more than one camera, so it cannot be matched "
                    f"by index either. {id_sets}"
                ),
            )
        calibration_by_index[camera.index] = camera

    live_ids_set = set(live_camera_ids)
    bound_by_index: dict[CameraIdString, CameraModel] = {}
    claimed_calibration_ids: set[str] = set()
    for live_id, live_index in live_camera_indices.items():
        candidate = calibration_by_index.get(live_index)
        if candidate is None:
            return _unmatched_binding(
                live_camera_ids=live_camera_ids,
                calibration_camera_ids=calibration_camera_ids,
                reason=(
                    f"No live camera id matched the calibration, and live camera {live_id!r} "
                    f"(index {live_index}) has no calibration camera at that index. {id_sets}"
                ),
            )
        if candidate.id in claimed_calibration_ids:
            return _unmatched_binding(
                live_camera_ids=live_camera_ids,
                calibration_camera_ids=calibration_camera_ids,
                reason=(
                    f"No live camera id matched the calibration, and matching by index would "
                    f"bind calibration camera {candidate.id!r} to more than one live camera. "
                    f"{id_sets}"
                ),
            )
        # The overlap guard: this calibration camera's id belongs to a DIFFERENT live
        # camera, so the two id spaces overlap and the index order is provably not a
        # relabelling of the same rig. Binding it here is how one calibration entry ends
        # up serving two cameras at once.
        if candidate.id != live_id and candidate.id in live_ids_set:
            return _unmatched_binding(
                live_camera_ids=live_camera_ids,
                calibration_camera_ids=calibration_camera_ids,
                reason=(
                    f"No live camera id matched the calibration, and matching by index would "
                    f"bind calibration camera {candidate.id!r} to live camera {live_id!r} while "
                    f"{candidate.id!r} is itself a live camera. The id sets overlap, so the "
                    f"index order is not a relabelling of the same rig. {id_sets}"
                ),
            )
        bound_by_index[live_id] = candidate
        claimed_calibration_ids.add(candidate.id)

    index_pairs = "; ".join(
        f"{live_id} (index {live_camera_indices[live_id]}) -> {model.id}"
        for live_id, model in bound_by_index.items()
    )
    return CalibrationBinding(
        by_live_id=dict(bound_by_index),
        kind=CalibrationMatchKind.INDEX,
        applicable=True,
        reason=(
            f"No live camera id matched the calibration, but every live camera bound to a "
            f"distinct calibration camera by index: {index_pairs}. The physical camera behind "
            f"an index can change — recalibrate if 3D looks wrong."
        ),
        live_camera_ids=live_camera_ids,
        calibration_camera_ids=calibration_camera_ids,
    )
