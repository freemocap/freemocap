import { describe, it, expect } from 'vitest';
import {
    settingsSlice,
    serverSettingsUpdated,
    serverSettingsCleared,
    ServerSettingsState,
} from '@/store/slices/settings/settings-slice';
import type {
    FreeMoCapSettings,
    SettingsStateMessage,
} from '@/store/slices/settings/settings-types';

const reducer = settingsSlice.reducer;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeSettings(overrides?: Partial<FreeMoCapSettings>): FreeMoCapSettings {
    return {
        cameras: {},
        pipeline: {
            config: null,
            is_connected: false,
            pipeline_id: null,
            camera_group_id: null,
            is_paused: false,
        },
        calibration: {
            config: {
                calibration_recording_folder: null,
                charuco_board_x_squares: 5,
                charuco_board_y_squares: 3,
                charuco_square_length: 1,
                solver_method: 'anipose',
                use_groundplane: false,
                pyceres_solver_config: {},
            },
            is_recording: false,
            recording_progress: 0,
            last_recording_path: null,
            has_calibration_toml: false,
        },
        mocap: {
            config: {
                detector: {},
                skeleton_filter: {
                    min_cutoff: 0.01,
                    beta: 0.5,
                    d_cutoff: 1.0,
                    fabrik_tolerance: 1e-4,
                    fabrik_max_iterations: 20,
                    height_meters: 1.75,
                    noise_sigma: 0.015,
                    estimator_config: {
                        max_samples: 500,
                        min_samples_for_full_confidence: 100,
                        iqr_confidence_sensitivity: 10.0,
                    },
                    max_reprojection_error_px: 60.0,
                    max_velocity_m_per_s: 50.0,
                    max_rejected_streak: 3,
                },
            },
            is_recording: false,
            recording_progress: 0,
            last_recording_path: null,
        },
        ...overrides,
    };
}

function makeStateMessage(
    version: number,
    settingsOverrides?: Partial<FreeMoCapSettings>,
): SettingsStateMessage {
    return {
        message_type: 'settings/state',
        settings: makeSettings(settingsOverrides),
        version,
    };
}

const initialState: ServerSettingsState = {
    settings: null,
    version: -1,
    lastUpdated: null,
    isInitialized: false,
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('settingsSlice', () => {
    it('has correct initial state', () => {
        const state = reducer(undefined, { type: 'unknown' });
        expect(state.settings).toBeNull();
        expect(state.version).toBe(-1);
        expect(state.lastUpdated).toBeNull();
        expect(state.isInitialized).toBe(false);
    });

    describe('serverSettingsUpdated', () => {
        it('applies a settings/state message with version > current', () => {
            const msg = makeStateMessage(1);
            const state = reducer(initialState, serverSettingsUpdated(msg));
            expect(state.settings).toEqual(msg.settings);
            expect(state.version).toBe(1);
            expect(state.isInitialized).toBe(true);
            expect(state.lastUpdated).not.toBeNull();
        });

        it('ignores a settings/state message with version <= current', () => {
            const firstMsg = makeStateMessage(5);
            const state1 = reducer(initialState, serverSettingsUpdated(firstMsg));

            const staleMsg = makeStateMessage(3, {
                calibration: {
                    ...makeSettings().calibration,
                    is_recording: true,
                },
            });
            const state2 = reducer(state1, serverSettingsUpdated(staleMsg));

            // Should not have changed
            expect(state2.version).toBe(5);
            expect(state2.settings!.calibration.is_recording).toBe(false);
        });

        it('ignores a settings/state message with same version', () => {
            const msg = makeStateMessage(5);
            const state1 = reducer(initialState, serverSettingsUpdated(msg));

            const sameVersionMsg = makeStateMessage(5, {
                calibration: {
                    ...makeSettings().calibration,
                    is_recording: true,
                },
            });
            const state2 = reducer(state1, serverSettingsUpdated(sameVersionMsg));
            expect(state2.settings!.calibration.is_recording).toBe(false);
        });

        it('applies newer version after an older one', () => {
            const msg1 = makeStateMessage(1);
            const state1 = reducer(initialState, serverSettingsUpdated(msg1));

            const msg2 = makeStateMessage(2, {
                calibration: {
                    ...makeSettings().calibration,
                    is_recording: true,
                },
            });
            const state2 = reducer(state1, serverSettingsUpdated(msg2));
            expect(state2.version).toBe(2);
            expect(state2.settings!.calibration.is_recording).toBe(true);
        });
    });

    describe('serverSettingsCleared', () => {
        it('resets to initial state', () => {
            const msg = makeStateMessage(5);
            const populated = reducer(initialState, serverSettingsUpdated(msg));
            expect(populated.isInitialized).toBe(true);

            const cleared = reducer(populated, serverSettingsCleared());
            expect(cleared.settings).toBeNull();
            expect(cleared.version).toBe(-1);
            expect(cleared.lastUpdated).toBeNull();
            expect(cleared.isInitialized).toBe(false);
        });
    });
});
