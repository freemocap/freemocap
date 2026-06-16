export type CalibrationSolverMethod = 'anipose' | 'pyceres';

export interface CharucoBoardConfig {
    squares_x: number;
    squares_y: number;
    square_length_mm: number;
}

export interface CalibrationConfig {
    charucoBoard: CharucoBoardConfig;
    minSharedViewsPerCamera: number;
    autoStopOnMinViewCount: boolean;
    solverMethod: CalibrationSolverMethod;
    useGroundplane: boolean;
}

export interface CalibrationCameraData {
    id: string;
    name: string;
    size: [number, number];
    matrix: number[][];
    distortions: number[];
    rotation: [number, number, number];
    translation: [number, number, number];
    world_orientation: number[][];
    world_position: [number, number, number];
}

export interface LoadedCalibration {
    path: string;
    mtimeMs: number;
    cameras: CalibrationCameraData[];
    metadata: Record<string, any> | null;
}
