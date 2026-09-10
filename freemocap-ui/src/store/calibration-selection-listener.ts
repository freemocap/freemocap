import {createListenerMiddleware} from '@reduxjs/toolkit';
import type {RootState} from './root-state-types';
import {applyRealtimePipeline} from './slices/realtime/realtime-thunks';
import {restoreCalibrationSelection} from './slices/calibration/calibration-thunks';

export const calibrationSelectionListenerMiddleware = createListenerMiddleware();

const startListening = calibrationSelectionListenerMiddleware.startListening.withTypes<RootState>();
startListening({
    predicate: (action, current, previous) => !restoreCalibrationSelection.fulfilled.match(action)
        && !restoreCalibrationSelection.rejected.match(action)
        && current.calibration.loadedCalibration !== previous.calibration.loadedCalibration,
    effect: (_, api) => {
        const state = api.getState();
        if (!state.realtime.isConnected || state.calibration.loadRequestId) return;
        void api.dispatch(applyRealtimePipeline({
            ...state.realtime.pipelineConfig,
            aggregator_config: {
                ...state.realtime.pipelineConfig.aggregator_config,
                calibration_toml_path: state.calibration.loadedCalibration?.path ?? null,
            },
        }));
    },
});
