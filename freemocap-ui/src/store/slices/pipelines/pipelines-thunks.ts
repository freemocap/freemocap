import {createAsyncThunk} from '@reduxjs/toolkit';
import {serverUrls} from '@/constants/server-urls';

export const stopPipeline = createAsyncThunk(
    'pipelines/stopPipeline',
    async (pipelineId: string, {rejectWithValue}) => {
        try {
            const res = await fetch(serverUrls.endpoints.stopPipeline(pipelineId), {method: 'DELETE'});
            if (!res.ok) {
                const text = await res.text();
                console.error(`[pipelines] stop pipeline ${pipelineId} failed (${res.status}): ${text}`);
                return rejectWithValue(pipelineId);
            }
        } catch (e) {
            console.error(`[pipelines] stop pipeline ${pipelineId} network error:`, e);
            return rejectWithValue(pipelineId);
        }
        return pipelineId;
    },
);

export const stopAllPipelines = createAsyncThunk(
    'pipelines/stopAllPipelines',
    async (_, {rejectWithValue}) => {
        try {
            const res = await fetch(serverUrls.endpoints.stopAllPipelines, {method: 'DELETE'});
            if (!res.ok) {
                const text = await res.text();
                console.error(`[pipelines] stop all pipelines failed (${res.status}): ${text}`);
                return rejectWithValue(null);
            }
        } catch (e) {
            console.error('[pipelines] stop all pipelines network error:', e);
            return rejectWithValue(null);
        }
    },
);
