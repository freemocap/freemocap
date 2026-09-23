import {createAsyncThunk} from '@reduxjs/toolkit';
import type {RootState} from '@/store/root-state-types';
import {serverUrls} from '@/constants/server-urls';
import {getDetailedErrorMessage} from '@/store/slices/thunk-helpers';
import {
    CalibrationTransformTypeSchema,
    CalibrationUpdateRequestSchema,
    LoadedCalibrationSchema,
    type LoadedCalibration,
    type CalibrationUpdateRequest,
} from './calibration-types';
import {
    transformFields, transformFromFields, TransformRepresentation,
} from '@/components/mocap-setup/reference-transform';

export function matchesSavedManualOffset(
    request: CalibrationUpdateRequest, matrix: readonly number[] | null,
): boolean {
    const manual = request.transformations.filter(
        entry => entry.operation === CalibrationTransformTypeSchema.enum.manual,
    );
    if (!matrix || matrix.length !== 16 || manual.length !== 1) return false;
    const saved = transformFields(transformFromFields(
        [...manual[0].translation_mm, ...manual[0].quaternion_wxyz],
        TransformRepresentation.Quaternion,
    ), TransformRepresentation.Matrix);
    return matrix.every((value, index) => Math.abs(value - saved[index]) <= 1e-8);
}

export const saveCalibrationTransform = createAsyncThunk<
    LoadedCalibration, CalibrationUpdateRequest | void, {state: RootState; rejectValue: string}
>(
    'calibration/saveTransform',
    async (processedRequest, {getState, rejectWithValue}) => {
        try {
            const state = getState();
            const calibration = state.calibration.loadedCalibration;
            const offset = state.realtime.pipelineConfig.aggregator_config.reference_transform;
            if (!calibration) throw new Error('Select a calibration before saving.');
            let request: CalibrationUpdateRequest;
            if (processedRequest) {
                request = CalibrationUpdateRequestSchema.parse(processedRequest);
                if (request.path !== calibration.path
                    || request.expected_mtime_ms !== calibration.mtimeMs) {
                    throw new Error('Select the unchanged source calibration used by this processing run.');
                }
            } else {
                if (!offset) throw new Error('Define a transform before saving.');
                const fields = transformFields(
                    transformFromFields(offset.matrix, TransformRepresentation.Matrix),
                    TransformRepresentation.Quaternion,
                );
                request = CalibrationUpdateRequestSchema.parse({
                    path: calibration.path,
                    expected_mtime_ms: calibration.mtimeMs,
                    transformations: [{
                        operation: CalibrationTransformTypeSchema.enum.manual,
                        translation_mm: fields.slice(0, 3),
                        quaternion_wxyz: fields.slice(3),
                    }],
                });
            }
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
        condition: (processedRequest, {getState}) => {
            const state = getState();
            return !state.calibration.isSaving
                && !state.calibration.isLoading
                && !state.calibration.isRecording
                && !state.calibration.loadRequestId
                && !state.realtime.isLoading
                && (!processedRequest || !state.mocap.isLoading);
        },
    },
);
