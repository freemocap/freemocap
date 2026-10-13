// Run: node src/components/pipeline-progress/run-operation-progress-tests.mjs
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {renderToStaticMarkup} from 'react-dom/server';
import {TaskRegistrySnapshotSchema, type TaskOperation} from '@/services/server/transport/message-contract';
import reducer, {taskSnapshotReceived, selectGroupedPipelinesAll} from '@/store/slices/pipelines/pipelines-slice';
import ProcessingTiming from './ProcessingTiming';
import OperationProgressBars from './OperationProgressBars';

const operation = (operation_id: string, changes: Partial<TaskOperation> = {}): TaskOperation => ({
    operation_id, label: operation_id, status: 'running', progress_fraction: null,
    completed: null, total: null, unit: null, detail: '', elapsed_seconds: null, seconds_per_motion_frame: null, ...changes,
});
function snapshot(revision: number, operations: TaskOperation[], status = 'running') {
    return TaskRegistrySnapshotSchema.parse({server_instance_id: '20000000-0000-4000-8000-000000000003',
        revision, recording_owners: [], tasks: [{task_id: 'recording', revision: revision + 1,
            task_type: 'mocap', recording: {base_directory: '/test', recording_name: 'sample', full_path: '/test/sample'},
            status, progress: {phase: status === 'running' ? 'exporting_csv' : 'complete', progress_fraction: null, detail: ''},
            operations, cameras: [], created_at: '2026-10-12T00:00:00Z', updated_at: '2026-10-12T00:01:00Z'}]});
}

test('snapshot preserves independent completed, running and failed rows without completing the run', () => {
    const first = snapshot(0, [operation('CSV', {progress_fraction: 0.3}), operation('Blender')]);
    let state = reducer(undefined, taskSnapshotReceived(first));
    const next = snapshot(1, [operation('CSV', {status: 'complete', progress_fraction: 1}), operation('Blender'), operation('NPZ', {status: 'failed'})]);
    state = reducer(state, taskSnapshotReceived(next));
    assert.deepEqual(state.activePipelines.recording.operations, next.tasks[0].operations);
    const groups = selectGroupedPipelinesAll({pipelines: state} as Parameters<typeof selectGroupedPipelinesAll>[0]);
    assert.equal(groups[0].isActive, true);
    assert.equal(groups[0].isComplete, false);
    assert.deepEqual(reducer(state, taskSnapshotReceived(first)), state, 'stale snapshots cannot replace newer bars');
    state = reducer(state, taskSnapshotReceived(snapshot(2, next.tasks[0].operations, 'complete')));
    assert.deepEqual(state.activePipelines.recording.operations, next.tasks[0].operations, 'terminal snapshots retain backend rows');
});

test('bars show independent percentages, real counts and unmeasured work without invented percentages', () => {
    const html = renderToStaticMarkup(<OperationProgressBars operations={[
        operation('Save CSV', {progress_fraction: 0.25, completed: 1, total: 4, unit: 'channels'}),
        operation('Export Blender'), operation('Save NPY', {status: 'complete', progress_fraction: 1}),
        operation('Save NPZ', {status: 'failed'}), operation('Save FBX', {status: 'cancelled'}),
        operation('Save BVH', {status: 'waiting'}),
    ]}/>);
    assert.equal((html.match(/role="progressbar"/g) ?? []).length, 6);
    assert.equal((html.match(/aria-valuenow=/g) ?? []).length, 2);
    assert.match(html, /1 \/ 4 channels/);
    for (const text of ['Running', 'Complete', 'Failed', 'Stopped', 'Waiting']) assert.ok(html.includes(text));
    assert.equal((html.match(/sub-progress-indeterminate/g) ?? []).length, 1);
});

test('cancelled run uses the backend status even if its legacy phase says failed', () => {
    const raw = snapshot(0, [operation('CSV', {status: 'cancelled'})], 'cancelled');
    raw.tasks[0].progress.phase = 'failed';
    const state = reducer(undefined, taskSnapshotReceived(raw));
    const group = selectGroupedPipelinesAll({pipelines: state} as Parameters<typeof selectGroupedPipelinesAll>[0])[0];
    assert.equal(group.isActive, false);
    assert.equal(group.isFailed, false);
    assert.equal(group.isComplete, false);
});

test('transport rejects invalid operation fractions and unknown states', () => {
    assert.throws(() => snapshot(0, [operation('CSV', {progress_fraction: 2})]));
    const raw = snapshot(0, []);
    const invalid = {...raw, tasks: [{...raw.tasks[0], operations: [{...operation('CSV'), status: 'guessing'}]}]};
    assert.equal(TaskRegistrySnapshotSchema.safeParse(invalid).success, false);
});


test('elapsed times and motion-frame rates come directly from backend snapshots', () => {
    const raw = snapshot(0, [operation('Save CSV', {status: 'complete', progress_fraction: 1, elapsed_seconds: 42.6, seconds_per_motion_frame: 0.0384})], 'complete');
    raw.tasks[0].timing = {elapsed_seconds: 137, motion_frame_count: 1108, seconds_per_motion_frame: 0.124};
    const state = reducer(undefined, taskSnapshotReceived(raw));
    assert.deepEqual(state.activePipelines.recording.timing, raw.tasks[0].timing);
    const rows = renderToStaticMarkup(<OperationProgressBars operations={raw.tasks[0].operations}/>);
    assert.match(rows, /42.6 s/);
    assert.match(rows, /38.4 ms \/ mocap frame/);
    const total = renderToStaticMarkup(<ProcessingTiming timing={state.activePipelines.recording.timing!} running={false}/>);
    assert.match(total, /2 m 17 s/);
    assert.match(total, /124 ms \/ motion-capture frame/);
    assert.match(total, /1,108/);
});

test('older snapshots and unknown counts do not invent elapsed times or motion-frame rates', () => {
    const raw = snapshot(0, []);
    const legacy = {...raw, tasks: raw.tasks.map(({timing, ...task}) => task)};
    assert.equal(TaskRegistrySnapshotSchema.parse(legacy).tasks[0].timing, null);
    assert.equal(renderToStaticMarkup(<ProcessingTiming timing={null} running={false}/>), '');
    const html = renderToStaticMarkup(<ProcessingTiming timing={{elapsed_seconds: 5, motion_frame_count: null, seconds_per_motion_frame: null}} running={false}/>);
    assert.match(html, /5 s/);
    assert.ok(!html.includes('frame'));
});
