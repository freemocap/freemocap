import {test, expect} from '@playwright/test';
import {build} from 'esbuild';
import path from 'node:path';

test.use({channel: process.env.PLAYWRIGHT_CHANNEL});

test('task state rebuilds from snapshots and rejects stale revisions', async ({page}) => {
    const errors: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.route('http://tasks.test/', route => route.fulfill({contentType: 'text/html', body: '<html></html>'}));
    await page.goto('http://tasks.test/');
    await page.setContent('<output id="result"></output>');
    const bundle = await build({
        stdin: {resolveDir: path.resolve('.'), loader: 'ts', contents: `
            import {pipelinesSlice, taskSnapshotReceived, allPipelinesCleared, pipelineDismissed, pipelineSnackbarHidden} from './src/store/slices/pipelines/pipelines-slice';
            function assert(value: boolean, message: string): void {if (!value) throw new Error(message);}
            const task = {task_id: 'parent:with:colons', task_type: 'calibration', revision: 1, status: 'running',
                recording: {base_directory: '/test', recording_name: 'recording', full_path: '/test/recording'},
                progress: {phase: 'running_solver', progress_fraction: null, detail: 'Solving'},
                cameras: [{node_id: 'opaque-node', camera_id: 'camera:identity',
                    progress: {phase: 'processing_images', progress_fraction: .5, detail: 'Detecting'}}],
                created_at: '2026-09-10T00:00:00Z', updated_at: '2026-09-10T00:00:00Z'};
            const snapshot = {recording_owners: [], server_instance_id: '10000000-0000-4000-8000-000000000000', revision: 7, tasks: [task]};
            const reduce = pipelinesSlice.reducer;
            const state = reduce(undefined, taskSnapshotReceived(snapshot));
            assert(state.activePipelines['opaque-node'].basePipelineId === task.task_id, 'Parent identity was inferred incorrectly');
            assert(state.activePipelines['opaque-node'].cameraId === 'camera:identity', 'Camera identity was lost');
            assert(state.activePipelines[task.task_id].progress === null, 'Unknown progress became zero');
            assert(reduce(state, taskSnapshotReceived(snapshot)) === state, 'Duplicate changed state');
            assert(reduce(state, taskSnapshotReceived({...snapshot, revision: 6, tasks: []})) === state, 'Stale snapshot changed state');
            const complete = {...snapshot, revision: 8, tasks: [{...task, status: 'complete',
                progress: {phase: 'complete', progress_fraction: 1, detail: 'Done'}}]};
            const dismissed = reduce(reduce(state, taskSnapshotReceived(complete)), allPipelinesCleared());
            assert(dismissed.activePipelines[task.task_id].phase === 'complete', 'Dismiss discarded server state');
            assert(dismissed.dismissedBasePipelineIds.includes(task.task_id), 'Completed task was not dismissed');
            const individuallyDismissed = reduce(dismissed, pipelineDismissed('already-dismissed'));
            const clearedAgain = reduce(individuallyDismissed, allPipelinesCleared());
            assert(clearedAgain.dismissedBasePipelineIds.includes('already-dismissed'), 'Clear erased a dismissal');
            const running = {...task, task_id: 'new-task', cameras: [{...task.cameras[0], node_id: 'finished-camera', progress: {phase: 'complete', progress_fraction: 1, detail: 'Done'}}]};
            const withNewTask = reduce(dismissed, taskSnapshotReceived({...snapshot, revision: 9, tasks: [...complete.tasks, running]}));
            const closed = reduce(withNewTask, pipelineSnackbarHidden());
            assert(closed.dismissedBasePipelineIds.includes(task.task_id), 'Close restored completed task');
            assert(!closed.dismissedBasePipelineIds.includes('new-task'), 'Finished camera hid a running parent');
            const restarted = reduce(dismissed, taskSnapshotReceived({...snapshot,
                server_instance_id: '20000000-0000-4000-8000-000000000000', revision: 0, tasks: []}));
            assert(Object.keys(restarted.activePipelines).length === 0, 'Restart retained old tasks');
            assert(restarted.dismissedBasePipelineIds.length === 0, 'Restart retained dismissals');
            document.getElementById('result')!.textContent = 'passed';
        `},
        bundle: true, write: false, format: 'esm', alias: {'@': path.resolve('src')},
        plugins: [{name: 'task-command-boundary', setup(builder) {
            builder.onResolve({filter: /pipelines-thunks$/}, () => ({path: 'commands', namespace: 'commands'}));
            builder.onLoad({filter: /.*/, namespace: 'commands'}, () => ({loader: 'ts', contents: `
                import {createAsyncThunk} from '@reduxjs/toolkit';
                export const stopPipeline = createAsyncThunk('pipelines/stopPipeline', async (): Promise<void> => {});
                export const stopAllPipelines = createAsyncThunk('pipelines/stopAllPipelines', async (): Promise<void> => {});
            `, resolveDir: path.resolve('.')}));
        }}],
    });
    await page.addScriptTag({content: bundle.outputFiles[0].text, type: 'module'});
    await expect(page.locator('#result')).toHaveText('passed');
    expect(errors).toEqual([]);
});


