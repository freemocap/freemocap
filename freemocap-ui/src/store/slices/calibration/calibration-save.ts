import {createAsyncThunk} from '@reduxjs/toolkit';
import type {RootState} from '@/store/root-state-types';
import {serverUrls} from '@/constants/server-urls';
import {getDetailedErrorMessage} from '@/store/slices/thunk-helpers';
import {
    CalibrationTransformTypeSchema,
    CalibrationUpdateRequestSchema,
    LoadedCalibrationSchema,
    type LoadedCalibration,
} from './calibration-types';
import {
    transformFields, transformFromFields, TransformRepresentation,
} from '@/components/mocap-setup/reference-transform';

export const saveCalibrationTransform = createAsyncThunk<
    LoadedCalibration, void, {state: RootState; rejectValue: string}
>(
    'calibration/saveTransform',
    async (_, {getState, rejectWithValue}) => {
        try {
            const state = getState();
            const calibration = state.calibration.loadedCalibration;
            const offset = state.realtime.pipelineConfig.aggregator_config.reference_transform;
            if (!calibration || !offset) {
                throw new Error('Select a calibration and define a transform before saving.');
            }
            const fields = transformFields(
                transformFromFields(offset.matrix, TransformRepresentation.Matrix),
                TransformRepresentation.Quaternion,
            );
            const request = CalibrationUpdateRequestSchema.parse({
                path: calibration.path,
                expected_mtime_ms: calibration.mtimeMs,
                transformations: [{
                    operation: CalibrationTransformTypeSchema.enum.manual,
                    translation_mm: fields.slice(0, 3),
                    quaternion_wxyz: fields.slice(3),
                }],
            });
            const response = await fetch(serverUrls.endpoints.calibrationTransform, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(request),
            });
            if (!response.ok) throw new Error(await getDetailedErrorMessage(response));
            return LoadedCalibrationSchema.parse(await response.json());
        } catch (error) {
            return rejectWithValue(error instanceof Error ? error.message : String(error));
        }
    },
    {
        condition: (_, {getState}) => {
            const state = getState();
            return !state.calibration.isSaving
                && !state.calibration.isLoading
                && !state.calibration.isRecording
                && !state.calibration.loadRequestId
                && !state.realtime.isLoading;
        },
    },
);
