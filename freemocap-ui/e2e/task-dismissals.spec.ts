import {test, expect} from '@playwright/test';
import {build} from 'esbuild';
import path from 'node:path';

test.use({channel: process.env.PLAYWRIGHT_CHANNEL});

test('task dismissals survive a client reload and new server snapshots', async ({page}) => {
    page.on('pageerror', error => {throw error;});
    await page.route('http://localhost:53117/', route => route.fulfill({contentType: 'text/html', body: '<output id="result"></output>'}));
    await page.goto('http://localhost:53117/');
    const bundle = await build({stdin: {resolveDir: path.resolve('.'), loader: 'ts', contents: `
        import {store} from './src/store/store';
        import {taskSnapshotReceived, allPipelinesCleared} from './src/store/slices/pipelines/pipelines-slice';
        const server = '10000000-0000-4000-8000-000000000000';
        const task = {task_id:'finished-task',task_type:'calibration',revision:1,status:'complete',
            recording:{base_directory:'/test',recording_name:'recording',full_path:'/test/recording'},
            progress:{phase:'complete',progress_fraction:1,detail:'Done'},cameras:[],
            created_at:'2026-09-10T00:00:00Z',updated_at:'2026-09-10T00:00:00Z'};
        const restored = store.getState().pipelines.dismissedBasePipelineIds.includes(task.task_id);
        store.dispatch(taskSnapshotReceived({server_instance_id:server,revision:1,recording_owners:[],tasks:[task]}));
        if (restored) {
            store.dispatch(taskSnapshotReceived({server_instance_id:server,revision:2,recording_owners:[],tasks:[task,
                {...task,task_id:'running-task',status:'running',progress:{phase:'queued',progress_fraction:null,detail:'Queued'}}]}));
            const state = store.getState().pipelines;
            if (!state.dismissedBasePipelineIds.includes(task.task_id) || state.dismissedBasePipelineIds.includes('running-task') || !state.snackbarVisible)
                throw new Error('Restored dismissal or new task visibility was lost');
        } else store.dispatch(allPipelinesCleared());
        document.getElementById('result')!.textContent=restored?'restored':'dismissed';
    `}, bundle:true, write:false,format:'esm',alias:{'@':path.resolve('src')},loader:{'.yaml':'text'}});
    await page.addScriptTag({content:bundle.outputFiles[0].text,type:'module'});
    await expect(page.locator('#result')).toHaveText('dismissed');
    await page.reload();
    await page.addScriptTag({content:bundle.outputFiles[0].text,type:'module'});
    await expect(page.locator('#result')).toHaveText('restored');
});


