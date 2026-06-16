/** TypeScript interfaces matching the backend Pupil Labs msgspec Struct types.

These are the wire-format types received inside the ``pupil_data`` field
of ``frontend_payload`` WebSocket messages. All coordinates are in millimeters.
*/

/** 3D eyeball model data for a single eye (from ``pupil.<id>.3d`` topic). */
export interface Pupil3dEyeballData {
    /** Eye identifier: 0 = right, 1 = left. */
    eye_id: number;
    /** Pupil Capture timestamp in seconds. */
    timestamp: number;
    /** Detection confidence, range [0, 1]. */
    confidence: number;
    // -- 3D eyeball sphere --
    sphere_center_x: number;
    sphere_center_y: number;
    sphere_center_z: number;
    /** Eyeball radius in mm (fixed-size model, typically ~12 mm). */
    sphere_radius: number;
    // -- 3D pupil circle --
    circle_center_x: number;
    circle_center_y: number;
    circle_center_z: number;
    /** Gaze direction (normal vector of the 3D pupil circle). */
    circle_normal_x: number;
    circle_normal_y: number;
    circle_normal_z: number;
    /** 3D pupil circle radius in mm. */
    circle_radius: number;
    // -- Polar coordinates on the eyeball sphere --
    theta: number;
    phi: number;
    // -- Pupil diameter --
    /** 3D pupil diameter in mm. */
    pupil_diameter_mm: number;
}

/** 3D gaze data for a single eye (from ``gaze.3d.<id>.`` topic, post-calibration). */
export interface PupilGazeData {
    eye_id: number;
    timestamp: number;
    /** Gaze direction unit vector in scene-camera coordinates. */
    gaze_normal_x: number;
    gaze_normal_y: number;
    gaze_normal_z: number;
    /** 3D gaze intersection point (may be null if not available). */
    gaze_point_3d_x: number | null;
    gaze_point_3d_y: number | null;
    gaze_point_3d_z: number | null;
}

/** Combined per-frame pupil + gaze data for both eyes.

This is the ``pupil_data`` field inside ``frontend_payload``. Values are
the per-field median of all pupil samples received since the last camera frame
(typically ~4 samples at 120Hz pupil vs 30Hz camera).
*/
export interface PupilFramePayload {
    timestamp: number;
    eyeballs: Pupil3dEyeballData[];
    gazes: PupilGazeData[];
}
