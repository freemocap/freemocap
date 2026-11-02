import {serverClient} from '@/services/server/sdk';
import {createAsyncThunk} from '@reduxjs/toolkit';
import {RootState} from '@/store/root-state-types';
import {serverUrls} from '@/services';
import {getDetailedErrorMessage} from '@/store/slices/thunk-helpers';

interface DetectFfmpegResult {
    found: boolean;
    ffmpegPath: string | null;
    ffprobePath: string | null;
    message?: string | null;
}

export const detectFfmpeg = createAsyncThunk<
    DetectFfmpegResult,
    void,
    { state: RootState; rejectValue: string }
>(
    'ffmpeg/detect',
    async (_, {rejectWithValue}) => {
        try {
            const response = await serverClient().responses.detect_ffmpeg_freemocap_ffmpeg_detect_get();
            if (!response.ok) {
                return rejectWithValue(await getDetailedErrorMessage(response));
            }
            const data = await response.json();
            return {
                found: !!data.found,
                ffmpegPath: data.ffmpeg_path ?? null,
                ffprobePath: data.ffprobe_path ?? null,
                message: data.message ?? null,
            };
        } catch (e) {
            return rejectWithValue(e instanceof Error ? e.message : 'Unknown error');
        }
    },
    {
        condition: (_, {getState}) => !getState().ffmpeg.isDetecting,
    }
);
