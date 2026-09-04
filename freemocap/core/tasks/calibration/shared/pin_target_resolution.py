"""Resolve a user-supplied "pin this camera to the origin" id against a camera list.

This is a *config* lookup, not an identity-reconciliation problem: the operator named a
camera in `pin_camera_id` and we have to find it. Two ways in, both structured:

1. exact `CameraModel.id`;
2. a bare integer, treated as the structured `CameraModel.index`.

Nothing here parses a camera id for digits. Ids are opaque
(`current-work-plans/00-foundation/conventions.md`: "names are opaque identifiers; a
naming scheme that has to be regex-able is a design that lost its structure somewhere
upstream"). A miss is a hard error — the operator asked for a specific camera and it is
not there, so guessing is worse than stopping.

For reconciling a *loaded calibration* against the *live* camera set, see
`calibration_camera_binding.py`. That is a different question with different rules.
"""

from collections.abc import Sequence

from freemocap.core.tasks.calibration.shared.camera_model import CameraModel


class CameraIdMismatchError(KeyError):
    """A camera id could not be resolved against the candidate set."""


def resolve_pin_target_camera(
    *,
    pin_camera_id: str,
    cameras: Sequence[CameraModel],
    context: str = "",
) -> CameraModel:
    """Find the camera the operator named, by exact id or by structured index.

    Raises:
        CameraIdMismatchError: when no camera matches.
    """
    for camera in cameras:
        if camera.id == pin_camera_id:
            return camera

    if pin_camera_id.isdigit():
        wanted_index = int(pin_camera_id)
        for camera in cameras:
            if camera.index == wanted_index:
                return camera

    context_suffix = f" [{context}]" if context else ""
    raise CameraIdMismatchError(
        f"Could not resolve camera id {pin_camera_id!r} against "
        f"{[camera.id for camera in cameras]}{context_suffix}. Give an exact camera id, "
        f"or a bare integer naming a camera index "
        f"({sorted(camera.index for camera in cameras)})."
    )
