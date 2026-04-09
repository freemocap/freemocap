import {describe, expect, it} from 'vitest';
import {
    DEFAULT_ESTIMATOR_CONFIG,
    DEFAULT_REALTIME_FILTER_CONFIG,
    MEDIAPIPE_POSTHOC_PRESET,
    MEDIAPIPE_REALTIME_PRESET,
    mocapDetectorConfigReplaced,
    mocapDetectorConfigUpdated,
    mocapErrorCleared,
    mocapSlice,
    MocapState,
    resetMocapState,
    skeletonFilterConfigReplaced,
    skeletonFilterConfigUpdated,
} from '@/store/slices/mocap/mocap-slice';

const reducer = mocapSlice.reducer;

function getInitialState(): MocapState {
    return reducer(undefined, { type: 'unknown' });
}

// ---------------------------------------------------------------------------
// Initial state — defaults must match backend
// ---------------------------------------------------------------------------

describe('mocapSlice initial state', () => {
    it('has detector config matching MEDIAPIPE_REALTIME_PRESET', () => {
        const state = getInitialState();
        expect(state.config.detector).toEqual(MEDIAPIPE_REALTIME_PRESET);
    });

    it('has skeleton_filter config matching DEFAULT_REALTIME_FILTER_CONFIG', () => {
        const state = getInitialState();
        expect(state.config.skeleton_filter).toEqual(DEFAULT_REALTIME_FILTER_CONFIG);
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
});

// ---------------------------------------------------------------------------
// Default constants match backend values
// ---------------------------------------------------------------------------

describe('default constants match backend', () => {
    describe('MEDIAPIPE_REALTIME_PRESET', () => {
        // These must match MEDIAPIPE_TRACKER_REALTIME_PRESET in skellytracker
        it('has model_complexity 0', () => {
            expect(MEDIAPIPE_REALTIME_PRESET.model_complexity).toBe(0);
        });
        it('has static_image_mode false', () => {
            expect(MEDIAPIPE_REALTIME_PRESET.static_image_mode).toBe(false);
        });
        it('has smooth_landmarks true', () => {
            expect(MEDIAPIPE_REALTIME_PRESET.smooth_landmarks).toBe(true);
        });
    });

    describe('DEFAULT_ESTIMATOR_CONFIG', () => {
        // Must match EstimatorConfig defaults in bone_length_estimator.py
        it('has max_samples 500', () => {
            expect(DEFAULT_ESTIMATOR_CONFIG.max_samples).toBe(500);
        });
        it('has min_samples_for_full_confidence 100', () => {
            expect(DEFAULT_ESTIMATOR_CONFIG.min_samples_for_full_confidence).toBe(100);
        });
        it('has iqr_confidence_sensitivity 10.0', () => {
            expect(DEFAULT_ESTIMATOR_CONFIG.iqr_confidence_sensitivity).toBe(10.0);
        });
    });

    describe('DEFAULT_REALTIME_FILTER_CONFIG', () => {
        // Must match RealtimeFilterConfig defaults in realtime_skeleton_filter.py
        it('has min_cutoff 0.005', () => {
            expect(DEFAULT_REALTIME_FILTER_CONFIG.min_cutoff).toBe(0.005);
        });
        it('has beta 0.3', () => {
            expect(DEFAULT_REALTIME_FILTER_CONFIG.beta).toBe(0.3);
        });
        it('has d_cutoff 1.0', () => {
            expect(DEFAULT_REALTIME_FILTER_CONFIG.d_cutoff).toBe(1.0);
        });
        it('has height_meters 1.75', () => {
            expect(DEFAULT_REALTIME_FILTER_CONFIG.height_meters).toBe(1.75);
        });
        it('has noise_sigma 0.015', () => {
            expect(DEFAULT_REALTIME_FILTER_CONFIG.noise_sigma).toBe(0.015);
        });
        it('has max_reprojection_error_px 60.0', () => {
            expect(DEFAULT_REALTIME_FILTER_CONFIG.max_reprojection_error_px).toBe(60.0);
        });
        it('has max_velocity_m_per_s 50.0', () => {
            expect(DEFAULT_REALTIME_FILTER_CONFIG.max_velocity_m_per_s).toBe(50.0);
        });
        it('has max_rejected_streak 5', () => {
            expect(DEFAULT_REALTIME_FILTER_CONFIG.max_rejected_streak).toBe(5);
        });
        it('has max_prediction_frames 15', () => {
            expect(DEFAULT_REALTIME_FILTER_CONFIG.max_prediction_frames).toBe(15);
        });
        it('has prediction_velocity_decay 0.75', () => {
            expect(DEFAULT_REALTIME_FILTER_CONFIG.prediction_velocity_decay).toBe(0.75);
        });
    });
});

// ---------------------------------------------------------------------------
// Detector config reducers
// ---------------------------------------------------------------------------

describe('mocapDetectorConfigReplaced', () => {
    it('replaces entire detector config', () => {
        const state = getInitialState();
        const updated = reducer(state, mocapDetectorConfigReplaced(MEDIAPIPE_POSTHOC_PRESET));
        expect(updated.config.detector).toEqual(MEDIAPIPE_POSTHOC_PRESET);
        expect(updated.config.detector.model_complexity).toBe(2);
    });
});

describe('mocapDetectorConfigUpdated', () => {
    it('merges partial update into detector config', () => {
        const state = getInitialState();
        const updated = reducer(state, mocapDetectorConfigUpdated({
            model_complexity: 1,
        }));
        expect(updated.config.detector.model_complexity).toBe(1);
        // Other fields preserved
        expect(updated.config.detector.smooth_landmarks).toBe(true);
    });
});

// ---------------------------------------------------------------------------
// Skeleton filter config reducers
// ---------------------------------------------------------------------------

describe('skeletonFilterConfigReplaced', () => {
    it('replaces entire filter config', () => {
        const state = getInitialState();
        const customFilter = {
            ...DEFAULT_REALTIME_FILTER_CONFIG,
            beta: 0.99,
            max_rejected_streak: 10,
        };
        const updated = reducer(state, skeletonFilterConfigReplaced(customFilter));
        expect(updated.config.skeleton_filter.beta).toBe(0.99);
        expect(updated.config.skeleton_filter.max_rejected_streak).toBe(10);
    });
});

describe('skeletonFilterConfigUpdated', () => {
    it('merges partial update into filter config', () => {
        const state = getInitialState();
        const updated = reducer(state, skeletonFilterConfigUpdated({ beta: 0.1 }));
        expect(updated.config.skeleton_filter.beta).toBe(0.1);
        // Other fields preserved from DEFAULT_REALTIME_FILTER_CONFIG
        expect(updated.config.skeleton_filter.min_cutoff).toBe(0.005);
        expect(updated.config.skeleton_filter.max_rejected_streak).toBe(5);
    });
});

// ---------------------------------------------------------------------------
// Error handling
// ---------------------------------------------------------------------------

describe('mocapErrorCleared', () => {
    it('clears error', () => {
        const state: MocapState = { ...getInitialState(), error: 'oops' };
        const updated = reducer(state, mocapErrorCleared());
        expect(updated.error).toBeNull();
    });
});

// ---------------------------------------------------------------------------
// Reset
// ---------------------------------------------------------------------------

describe('resetMocapState', () => {
    it('resets to initial state', () => {
        const modified: MocapState = {
            ...getInitialState(),
            config: {
                detector: MEDIAPIPE_POSTHOC_PRESET,
                skeleton_filter: { ...DEFAULT_REALTIME_FILTER_CONFIG, beta: 99 },
            },
            isRecording: true,
            error: 'err',
        };
        const reset = reducer(modified, resetMocapState());
        expect(reset).toEqual(getInitialState());
    });
});

// ---------------------------------------------------------------------------
// Async thunk reducers
// ---------------------------------------------------------------------------

describe('startMocapRecording thunk reducers', () => {
    it('pending sets isLoading', () => {
        const state = getInitialState();
        const updated = reducer(state, { type: 'mocap/startRecording/pending' });
        expect(updated.isLoading).toBe(true);
        expect(updated.error).toBeNull();
    });

    it('fulfilled sets isRecording', () => {
        const state: MocapState = { ...getInitialState(), isLoading: true };
        const updated = reducer(state, {
            type: 'mocap/startRecording/fulfilled',
            payload: { success: true },
        });
        expect(updated.isLoading).toBe(false);
        expect(updated.isRecording).toBe(true);
        expect(updated.recordingProgress).toBe(0);
    });

    it('rejected sets error', () => {
        const state: MocapState = { ...getInitialState(), isLoading: true };
        const updated = reducer(state, {
            type: 'mocap/startRecording/rejected',
            payload: 'Network error',
        });
        expect(updated.isLoading).toBe(false);
        expect(updated.error).toBe('Network error');
    });
});
