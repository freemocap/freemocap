import {z} from 'zod';
import {CalibrationSolverMethodSchema, CalibrationCreationAlignmentMethodSchema, LoadedCalibrationSchema, type CalibrationSolverMethod} from '@freemocap/client/recording';
export * from '@freemocap/client/recording';

export enum CalibrationBoardMode { AUTO = "auto", EXPLICIT = "explicit" }


export const CALIBRATION_SOLVER_LABELS: Record<CalibrationSolverMethod, string> = {
    [CalibrationSolverMethodSchema.enum.anipose]: 'Anipose',
};

export interface CharucoBoardConfig {
    squares_x: number;
    squares_y: number;
    square_length_mm: number;
}

export interface CalibrationConfig {
    boardMode: CalibrationBoardMode;
    charucoBoard: CharucoBoardConfig;
    minSharedViewsPerCamera: number;
    autoStopOnMinViewCount: boolean;
    solverMethod: CalibrationSolverMethod;
    alignmentMethod: z.infer<typeof CalibrationCreationAlignmentMethodSchema> | null;
}

export const SceneCalibrationSchema = LoadedCalibrationSchema.pick({cameras: true});
export type SceneCalibration = z.infer<typeof SceneCalibrationSchema>;
export const CalibrationSceneSchema = z.object({
    calibration: SceneCalibrationSchema.nullable(),
    referenceTransform: z.array(z.number()).length(16).nullable(),
});
export type CalibrationScene = z.infer<typeof CalibrationSceneSchema>;
