import {createAsyncThunk} from '@reduxjs/toolkit';
import {serverUrls} from '@/constants/server-urls';
import type {RootState} from '@/store/root-state-types';
import {PipelineType, PipelinePhase} from './pipelines-slice';

export const stopPipeline = createAsyncThunk<string, string, {state: RootState}>(
    'pipelines/stopPipeline',
    async (pipelineId, {getState}) => {
        const pipeline = Object.values(getState().pipelines.activePipelines)
            .find(item => item.pipelineId.split(':')[0] === pipelineId);
        if (!pipeline?.pipelineType) throw new Error(`Missing task type for pipeline ${pipelineId}`);
        const base = serverUrls.getHttpUrl();
        const routes: Record<PipelineType, string> = {
            [PipelineType.MOCAP]: '/freemocap/mocap/posthoc/pipelines',
            [PipelineType.CALIBRATION]: '/freemocap/calibration/posthoc/pipelines',
            [PipelineType.SYNC]: '/freemocap/mocap/synchronization/jobs',
        };
        const response = await fetch(`${base}${routes[pipeline.pipelineType]}/${encodeURIComponent(pipelineId)}`, {method: 'DELETE'});
        if (!response.ok) throw new Error(await response.text());
        return pipelineId;
    },
);

export const stopAllPipelines = createAsyncThunk<void, void, {state: RootState}>(
    'pipelines/stopAllPipelines',
    async (_, {getState, dispatch}) => {
        const ids = [...new Set(Object.values(getState().pipelines.activePipelines)
            .filter(item => item.phase !== PipelinePhase.COMPLETE && item.phase !== PipelinePhase.FAILED)
            .map(item => item.pipelineId.split(':')[0]))];
        const results = await Promise.allSettled(ids.map(id => dispatch(stopPipeline(id)).unwrap()));
        const failures = results.filter(result => result.status === 'rejected');
        if (failures.length) throw new Error(`Cancellation failed for ${failures.length} pipeline(s)`);
    },
);
