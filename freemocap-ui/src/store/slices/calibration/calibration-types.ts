// calibration-types.ts
import { z } from 'zod';

// ==================== Constants ====================
export const BOARD_TYPES = ['5x3', '7x5', 'custom'] as const;

export type BoardType = typeof BOARD_TYPES[number];

// ==================== Calibration Configuration ====================
const CalibrationConfigSchema = z.object({
    boardType: z.enum(BOARD_TYPES),
    boardSize: z.object({
        rows: z.number().int().positive(),
        cols: z.number().int().positive(),
    }),
    squareSize: z.number().positive(),
    minSharedViews: z.number().int().positive(),
    autoProcess: z.boolean(),
    realtimeTracker: z.boolean(),
    calibrationPath: z.string(),
});

export type CalibrationConfig = z.infer<typeof CalibrationConfigSchema>;

// ==================== Store State ====================
export interface CalibrationState {
    config: CalibrationConfig;
    isRecording: boolean;
    recordingProgress: number;
    isLoading: boolean;
    error: string | null;
}

// ==================== API Types ====================
export interface StartRecordingRequest {
    config: CalibrationConfig;
}

export interface StartRecordingResponse {
    success: boolean;
    message?: string;
}

export interface CalibrateRecordingRequest {
    calibrationPath: string;
    config: Omit<CalibrationConfig, 'calibrationPath'>;
}

export interface CalibrateRecordingResponse {
    success: boolean;
    message?: string;
    results?: unknown; // Replace with actual calibration results type
}

// ==================== Helper Functions ====================
export function createDefaultCalibrationConfig(): CalibrationConfig {
    return {
        boardType: '7x5',
        boardSize: { rows: 7, cols: 5 },
        squareSize: 25,
        minSharedViews: 2,
        autoProcess: true,
        realtimeTracker: false,
        calibrationPath: '',
    };
}

export function getBoardSizeForType(boardType: BoardType): { rows: number; cols: number } {
    switch (boardType) {
        case '5x3':
            return { rows: 5, cols: 3 };
        case '7x5':
            return { rows: 7, cols: 5 };
        case 'custom':
            return { rows: 7, cols: 5 }; // Default for custom
    }
}
