import type {ThunkDispatch, UnknownAction} from '@reduxjs/toolkit';
import type {RootState} from '@/store/root-state-types';
import type {TaskRegistrySnapshot} from './transport/message-contract';
import {taskSnapshotReceived, PipelinePhase, PipelineType} from '@/store/slices/pipelines/pipelines-slice';
import {fetchPlaybackBundle, recordingPlaybackInvalidated} from '@/store/slices/playback-data/playback-data-slice';
import {loadCalibrationForRecording} from '@/store/slices/calibration/calibration-thunks';

export function applyTaskSnapshot(
    snapshot: TaskRegistrySnapshot,
    before: RootState['pipelines'],
    dispatch: ThunkDispatch<RootState, unknown, UnknownAction>,
): void {
    if (before.serverInstanceId === snapshot.server_instance_id && snapshot.revision <= before.registryRevision) return;
    dispatch(taskSnapshotReceived(snapshot));
    for (const owner of snapshot.recording_owners) {
        dispatch(recordingPlaybackInvalidated({recordingId: owner.recording.recording_name,
            recordingParentDirectory: owner.recording.base_directory}));
    }
    for (const owner of before.recordingOwners) {
        if (!snapshot.recording_owners.some(item => item.recording.full_path === owner.recording.full_path)) {
            void dispatch(fetchPlaybackBundle({recordingId: owner.recording.recording_name,
                recordingParentDirectory: owner.recording.base_directory}));
        }
    }
    for (const task of snapshot.tasks) {
        const previous = before.serverInstanceId === snapshot.server_instance_id ? before.activePipelines[task.task_id] : undefined;
        const previouslyTerminal = previous?.phase === PipelinePhase.COMPLETE || previous?.phase === PipelinePhase.FAILED;
        const blocked = snapshot.recording_owners.some(owner => owner.recording.full_path === task.recording.full_path);
        const wasBlocked = before.recordingOwners.some(owner => owner.recording.full_path === task.recording.full_path);
        if (task.status === 'complete' && !blocked && (!previouslyTerminal || wasBlocked)) {
            const recording = task.recording;
            void dispatch(fetchPlaybackBundle({recordingId: recording.recording_name,
                recordingParentDirectory: recording.base_directory}));
            if (task.task_type === PipelineType.CALIBRATION) {
                void dispatch(loadCalibrationForRecording({recordingId: recording.recording_name,
                    recordingParentDirectory: recording.base_directory}));
            }
        }
        if (task.task_type === PipelineType.MOCAP) {
            dispatch({type: 'mocap/posthocProgressReceived', payload: task.progress});
        } else {
            dispatch({type: 'calibration/calibrationPipelineProgressReceived', payload: task.progress});
        }
    }
}
