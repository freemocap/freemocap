"""msgspec Struct types for Pupil Labs 3D eyeball and gaze data.

These are wire-format types — they serialize to JSON automatically via
the existing msgspec encoder in the WebSocket relay, so adding a field
of these types to FrontendPayload Just Works.
"""

import msgspec


class Pupil3dEyeballData(msgspec.Struct):
    """3D eyeball model data from a single eye (from ``pupil.<id>.3d`` topic).

    All 3D coordinates are in millimeters in eye-camera space.
    """

    eye_id: int
    """Eye identifier: ``0`` (right) or ``1`` (left)."""

    timestamp: float
    """Pupil Capture timestamp in seconds."""

    confidence: float
    """Detection confidence, range [0, 1]."""

    # -- 3D eyeball sphere --
    sphere_center_x: float
    sphere_center_y: float
    sphere_center_z: float
    """Eyeball sphere center in mm."""

    sphere_radius: float
    """Eyeball radius in mm (fixed-size model, typically ~12 mm)."""

    # -- 3D pupil circle --
    circle_center_x: float
    circle_center_y: float
    circle_center_z: float
    """3D pupil circle center in mm."""

    circle_normal_x: float
    circle_normal_y: float
    circle_normal_z: float
    """Normal vector of the 3D pupil circle (i.e. gaze direction)."""

    circle_radius: float
    """3D pupil circle radius in mm."""

    # -- Polar coordinates on the eyeball sphere --
    theta: float
    """Pupil polar coordinate on the 3D eye model."""

    phi: float
    """Pupil polar coordinate on the 3D eye model."""

    # -- Pupil diameter --
    pupil_diameter_mm: float
    """3D pupil diameter in mm."""


class PupilGazeData(msgspec.Struct):
    """3D gaze data for a single eye (from ``gaze.3d.<id>.`` topic).

    Requires calibration. The gaze point is the intersection of the gaze
    vector with the scene camera plane.
    """

    eye_id: int
    """Eye identifier: ``0`` (right) or ``1`` (left)."""

    timestamp: float
    """Pupil Capture timestamp in seconds."""

    gaze_normal_x: float
    gaze_normal_y: float
    gaze_normal_z: float
    """Gaze direction unit vector in scene-camera coordinates."""

    gaze_point_3d_x: float | None = None
    gaze_point_3d_y: float | None = None
    gaze_point_3d_z: float | None = None
    """3D gaze intersection point in scene-camera coordinates (may be None if not available)."""


class PupilFramePayload(msgspec.Struct):
    """One combined frame of pupil + gaze data (both eyes).

    This is what gets attached to ``FrontendPayload.pupil_data`` after
    median aggregation across the samples received since the last camera frame.
    """

    timestamp: float
    """Pupil Capture timestamp of this combined frame."""

    eyeballs: list[Pupil3dEyeballData]
    """Per-eye 3D eyeball model data."""

    gazes: list[PupilGazeData]
    """Per-eye 3D gaze data (empty if calibration not performed)."""
