import {createAsyncThunk} from '@reduxjs/toolkit';
import {RootState} from '@/store/types';
import {serverUrls} from '@/services';
import {getDetailedErrorMessage} from '@/store/slices/thunk-helpers';

interface DetectBlenderResult {
    blenderExePath: string | null;
    found: boolean;
    message?: string | null;
}

export const detectBlender = createAsyncThunk<
    DetectBlenderResult,
    void,
    { state: RootState; rejectValue: string }
>(
    'blender/detect',
    async (_, {rejectWithValue}) => {
        try {
            const response = await fetch(serverUrls.endpoints.blenderDetect);
            if (!response.ok) {
                return rejectWithValue(await getDetailedErrorMessage(response));
            }
            const data = await response.json();
            return {
                blenderExePath: data.blender_exe_path ?? null,
                found: !!data.found,
                message: data.message ?? null,
            };
        } catch (e) {
            return rejectWithValue(e instanceof Error ? e.message : 'Unknown error');
        }
    }
);

interface ExportBlenderResult {
    success: boolean;
    message?: string | null;
    blenderFilePath?: string | null;
}

export const exportRecordingToBlender = createAsyncThunk<
    ExportBlenderResult,
    { recordingFolderPath: string } | void,
    { state: RootState; rejectValue: string }
>(
    'blender/export',
    async (arg, {getState, rejectWithValue}) => {
        try {
            const state = getState();
            const blender = state.blender;
            const recordingFolderPath =
                (arg && arg.recordingFolderPath) ||
                state.mocap.manualMocapRecordingPath ||
                state.mocap.lastMocapRecordingPath;

            if (!recordingFolderPath) {
                return rejectWithValue('No recording folder path available for Blender export');
            }

            const blenderExePath = blender.blenderExePath ?? blender.detectedBlenderExePath;

            const response = await fetch(serverUrls.endpoints.blenderExport, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    recordingFolderPath,
                    blenderExePath,
                    autoOpenBlendFile: blender.autoOpenBlendFile,
                }),
            });

            if (!response.ok) {
                return rejectWithValue(await getDetailedErrorMessage(response));
            }
            const data = await response.json();
            return {
                success: !!data.success,
                message: data.message ?? null,
                blenderFilePath: data.blender_file_path ?? null,
            };
        } catch (e) {
            return rejectWithValue(e instanceof Error ? e.message : 'Unknown error');
        }
    }
);
