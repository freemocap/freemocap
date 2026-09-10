import {createAsyncThunk} from '@reduxjs/toolkit';
import {serverUrls} from '@/constants/server-urls';
import type {RootState} from '@/store/root-state-types';
import {PipelineType} from './pipelines-slice';
import {TaskRegistrySnapshotSchema} from '@/services/server/transport/message-contract';
import {applyTaskSnapshot} from '@/services/server/task-progress';

export const fetchTaskSnapshot = createAsyncThunk<void, void, {state: RootState}>('pipelines/fetchTaskSnapshot', async (_, {dispatch, getState, signal}) => {
    const initialInstance = getState().pipelines.serverInstanceId;
    const response = await fetch(`${serverUrls.getHttpUrl()}/freemocap/posthoc/tasks`, {signal});
    if (!response.ok) throw new Error(await response.text());
    const snapshot = TaskRegistrySnapshotSchema.parse(await response.json());
    const current = getState().pipelines;
    if (current.serverInstanceId !== initialInstance && snapshot.server_instance_id !== current.serverInstanceId) return;
    applyTaskSnapshot(snapshot, current, dispatch);
});

export const stopPipeline = createAsyncThunk<string, string, {state: RootState}>(
    'pipelines/stopPipeline',
    async (pipelineId, {getState, dispatch}) => {
        const pipeline = Object.values(getState().pipelines.activePipelines)
            .find(item => item.basePipelineId === pipelineId);
        if (!pipeline?.pipelineType) throw new Error(`Missing task type for pipeline ${pipelineId}`);
        const base = serverUrls.getHttpUrl();
        const routes: Record<PipelineType, string> = {
            [PipelineType.MOCAP]: '/freemocap/mocap/posthoc/pipelines',
            [PipelineType.CALIBRATION]: '/freemocap/calibration/posthoc/pipelines',
            [PipelineType.SYNC]: '/freemocap/mocap/synchronization/jobs',
        };
        const response = await fetch(`${base}${routes[pipeline.pipelineType]}/${encodeURIComponent(pipelineId)}`, {method: 'DELETE'});
        if (!response.ok) throw new Error(await response.text());
        await dispatch(fetchTaskSnapshot()).unwrap();
        return pipelineId;
    },
);

export const stopAllPipelines = createAsyncThunk<void, void, {state: RootState}>(
    'pipelines/stopAllPipelines',
    async (_, {getState, dispatch}) => {
        const ids = [...new Set(Object.values(getState().pipelines.activePipelines)
            .filter(item => item.cameraId === null && item.completedAt === undefined)
            .map(item => item.basePipelineId))];
        const results = await Promise.allSettled(ids.map(id => dispatch(stopPipeline(id)).unwrap()));
        const failures = results.filter(result => result.status === 'rejected');
        if (failures.length) throw new Error(`Cancellation failed for ${failures.length} pipeline(s)`);
    },
);
