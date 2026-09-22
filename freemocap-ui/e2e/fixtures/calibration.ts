import type {LoadedCalibration} from '../../src/store/slices/calibration/calibration-types';

export function calibrationFixture(path: string): LoadedCalibration {
    return {
        path,
        mtimeMs: 1,
        cameras: [{
            id: 'camera',
            index: 0,
            image_size: [1280, 720],
            intrinsics: {
                fx: 1000, fy: 1000, cx: 640, cy: 360,
                k1: 0, k2: 0, p1: 0, p2: 0,
            },
            extrinsics: {
                quaternion_wxyz: [1, 0, 0, 0],
                translation: [0, 0, 0],
            },
            world_position: [0, 0, 0],
            world_orientation: [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
        }],
        metadata: {
            board: {
                squares_x: 5, squares_y: 3, square_length_mm: 50,
                marker_length_ratio: 0.65, aruco_dictionary_enum: 2,
                aruco_marker_length_mm: 32.5,
            },
            reprojection_error_px: 0.4,
            initial_cost: 12,
            final_cost: 3,
            n_iterations: 7,
            solver_time_seconds: 2.5,
            n_observations_used: 100,
            n_observations_rejected: 4,
            aligned: true,
            solver_method: null,
            recording_info: null,
            alignment_method: null,
            alignment_recording_id: null,
            alignment_result: null,
            transformation_history: [],
        },
    };
}
