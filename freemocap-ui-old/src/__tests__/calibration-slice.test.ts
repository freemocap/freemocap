import {describe, expect, it} from 'vitest';
import {
    calibrationConfigUpdated,
    CalibrationDirectoryInfo,
    calibrationDirectoryInfoUpdated,
    calibrationErrorCleared,
    calibrationProgressUpdated,
    calibrationSlice,
    CalibrationState,
    manualCalibrationRecordingPathChanged,
    manualCalibrationRecordingPathCleared,
    resetCalibrationState,
} from '@/store/slices/calibration/calibration-slice';

const reducer = calibrationSlice.reducer;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getInitialState(): CalibrationState {
    return reducer(undefined, { type: 'unknown' });
}

// ---------------------------------------------------------------------------
// Initial state
// ---------------------------------------------------------------------------

describe('calibrationSlice initial state', () => {
    it('has correct default config values matching backend defaults', () => {
        const state = getInitialState();
        // These MUST match CalibrationPipelineConfig defaults on the backend
        expect(state.config.charucoBoardXSquares).toBe(5);
        expect(state.config.charucoBoardYSquares).toBe(3);
        expect(state.config.charucoSquareLength).toBe(1);
        expect(state.config.solverMethod).toBe('anipose');
        expect(state.config.useGroundplane).toBe(false);
    });

    it('starts not recording', () => {
        const state = getInitialState();
        expect(state.isRecording).toBe(false);
        expect(state.recordingProgress).toBe(0);
    });

    it('starts with no error', () => {
        const state = getInitialState();
        expect(state.error).toBeNull();
    });

    it('starts with no loading', () => {
        const state = getInitialState();
        expect(state.isLoading).toBe(false);
    });
});

// ---------------------------------------------------------------------------
// calibrationConfigUpdated
// ---------------------------------------------------------------------------

describe('calibrationConfigUpdated', () => {
    it('merges partial config update', () => {
        const state = getInitialState();
        const updated = reducer(state, calibrationConfigUpdated({
            charucoBoardXSquares: 7,
        }));
        expect(updated.config.charucoBoardXSquares).toBe(7);
        // Other fields should be preserved
        expect(updated.config.charucoBoardYSquares).toBe(3);
        expect(updated.config.charucoSquareLength).toBe(1);
        expect(updated.config.solverMethod).toBe('anipose');
    });

    it('can update solver method', () => {
        const state = getInitialState();
        const updated = reducer(state, calibrationConfigUpdated({
            solverMethod: 'pyceres',
        }));
        expect(updated.config.solverMethod).toBe('pyceres');
    });

    it('can update useGroundplane', () => {
        const state = getInitialState();
        const updated = reducer(state, calibrationConfigUpdated({
            useGroundplane: true,
        }));
        expect(updated.config.useGroundplane).toBe(true);
    });

    it('can update multiple fields at once', () => {
        const state = getInitialState();
        const updated = reducer(state, calibrationConfigUpdated({
            charucoBoardXSquares: 9,
            charucoBoardYSquares: 7,
            charucoSquareLength: 39.5,
        }));
        expect(updated.config.charucoBoardXSquares).toBe(9);
        expect(updated.config.charucoBoardYSquares).toBe(7);
        expect(updated.config.charucoSquareLength).toBe(39.5);
    });
});

// ---------------------------------------------------------------------------
// Progress and error
// ---------------------------------------------------------------------------

describe('calibrationProgressUpdated', () => {
    it('sets recording progress', () => {
        const state = getInitialState();
        const updated = reducer(state, calibrationProgressUpdated(42.5));
        expect(updated.recordingProgress).toBe(42.5);
    });
});

describe('calibrationErrorCleared', () => {
    it('clears error', () => {
        const state: CalibrationState = {
            ...getInitialState(),
            error: 'something went wrong',
        };
        const updated = reducer(state, calibrationErrorCleared());
        expect(updated.error).toBeNull();
    });
});

// ---------------------------------------------------------------------------
// Manual recording path
// ---------------------------------------------------------------------------

describe('manual recording path', () => {
    it('sets manual path', () => {
        const state = getInitialState();
        const updated = reducer(state, manualCalibrationRecordingPathChanged('/custom/path'));
        expect(updated.manualCalibrationRecordingPath).toBe('/custom/path');
    });

    it('clears manual path', () => {
        const state: CalibrationState = {
            ...getInitialState(),
            manualCalibrationRecordingPath: '/custom/path',
        };
        const updated = reducer(state, manualCalibrationRecordingPathCleared());
        expect(updated.manualCalibrationRecordingPath).toBeNull();
    });
});

// ---------------------------------------------------------------------------
// Directory info
// ---------------------------------------------------------------------------

describe('calibrationDirectoryInfoUpdated', () => {
    it('stores directory info', () => {
        const state = getInitialState();
        const info: CalibrationDirectoryInfo = {
            exists: true,
            canRecord: true,
            canCalibrate: true,
            cameraCalibrationTomlPath: '/tmp/cal/calibration.toml',
            hasSynchronizedVideos: true,
            hasVideos: true,
            errorMessage: null,
        };
        const updated = reducer(state, calibrationDirectoryInfoUpdated(info));
        expect(updated.directoryInfo).toEqual(info);
    });
});

// ---------------------------------------------------------------------------
// Reset
// ---------------------------------------------------------------------------

describe('resetCalibrationState', () => {
    it('resets everything to initial state', () => {
        const modified: CalibrationState = {
            config: {
                liveTrackCharuco: false,
                charucoBoardXSquares: 9,
                charucoBoardYSquares: 7,
                charucoSquareLength: 40,
                minSharedViewsPerCamera: 300,
                autoStopOnMinViewCount: false,
                solverMethod: 'pyceres',
                useGroundplane: true,
            },
            isRecording: true,
            recordingProgress: 50,
            isLoading: true,
            error: 'some error',
            lastCalibrationRecordingPath: '/some/path',
            manualCalibrationRecordingPath: '/manual/path',
            directoryInfo: null,
        };
        const reset = reducer(modified, resetCalibrationState());
        const fresh = getInitialState();
        expect(reset).toEqual(fresh);
    });
});

// ---------------------------------------------------------------------------
// Async thunk reducers (pending/fulfilled/rejected)
// ---------------------------------------------------------------------------

describe('startCalibrationRecording thunk reducers', () => {
    it('pending sets isLoading and clears error', () => {
        const state: CalibrationState = {
            ...getInitialState(),
            error: 'old error',
        };
        const updated = reducer(state, {
            type: 'calibration/startRecording/pending',
        });
        expect(updated.isLoading).toBe(true);
        expect(updated.error).toBeNull();
    });

    it('fulfilled sets isRecording and resets progress', () => {
        const state: CalibrationState = {
            ...getInitialState(),
            isLoading: true,
        };
        const updated = reducer(state, {
            type: 'calibration/startRecording/fulfilled',
            payload: { success: true },
        });
        expect(updated.isLoading).toBe(false);
        expect(updated.isRecording).toBe(true);
        expect(updated.recordingProgress).toBe(0);
    });

    it('fulfilled stores calibrationRecordingPath if provided', () => {
        const state: CalibrationState = {
            ...getInitialState(),
            isLoading: true,
        };
        const updated = reducer(state, {
            type: 'calibration/startRecording/fulfilled',
            payload: {
                success: true,
                calibrationRecordingPath: '/new/recording/path',
            },
        });
        expect(updated.lastCalibrationRecordingPath).toBe('/new/recording/path');
    });

    it('rejected sets error', () => {
        const state: CalibrationState = {
            ...getInitialState(),
            isLoading: true,
        };
        const updated = reducer(state, {
            type: 'calibration/startRecording/rejected',
            payload: 'Connection refused',
        });
        expect(updated.isLoading).toBe(false);
        expect(updated.error).toBe('Connection refused');
    });
});

describe('stopCalibrationRecording thunk reducers', () => {
    it('fulfilled stops recording', () => {
        const state: CalibrationState = {
            ...getInitialState(),
            isRecording: true,
            isLoading: true,
            recordingProgress: 80,
        };
        const updated = reducer(state, {
            type: 'calibration/stopRecording/fulfilled',
            payload: { success: true },
        });
        expect(updated.isLoading).toBe(false);
        expect(updated.isRecording).toBe(false);
        expect(updated.recordingProgress).toBe(0);
    });
});

describe('updateCalibrationConfigOnServer thunk reducers', () => {
    it('rejected sets error', () => {
        const state = getInitialState();
        const updated = reducer(state, {
            type: 'calibration/updateConfig/rejected',
            payload: 'Server error',
        });
        expect(updated.error).toBe('Server error');
    });
});
