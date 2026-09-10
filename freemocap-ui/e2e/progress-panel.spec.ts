import {test, expect} from '@playwright/test';
import {build} from 'esbuild';
import path from 'node:path';

test.use({channel: process.env.PLAYWRIGHT_CHANNEL});

test('progress panel stays bounded and clearing real cards survives new tasks', async ({page}) => {
    page.on('pageerror', error => {throw error;});
    await page.setViewportSize({width: 1000, height: 700});
    await page.route('http://localhost:53117/', route => route.fulfill({contentType:'text/html',body:'<div id="root"></div>'}));
    await page.goto('http://localhost:53117/');
    const bundle = await build({stdin:{resolveDir:path.resolve('.'),loader:'tsx',contents:`
        import './src/styles/App.css';
        import React from 'react';
        import {createRoot} from 'react-dom/client';
        import {Provider} from 'react-redux';
        import {MemoryRouter} from 'react-router-dom';
        import {store} from './src/store/store';
        import {taskSnapshotReceived,pipelineSnackbarShown} from './src/store/slices/pipelines/pipelines-slice';
        import Panel from './src/components/pipeline-progress/PipelineProgressSnackbar';
        const tasks=Array.from({length:20},(_,index)=>({task_id:'task-'+index,task_type:'calibration',revision:1,status:'complete',
            recording:{base_directory:'/test',recording_name:'recording-'+index,full_path:'/test/recording-'+index},
            progress:{phase:'complete',progress_fraction:1,detail:'Finished'},cameras:[],created_at:'2026-09-10T00:00:00Z',updated_at:'2026-09-10T00:01:00Z'}));
        const snapshot={server_instance_id:'10000000-0000-4000-8000-000000000000',revision:1,recording_owners:[],tasks};
        store.dispatch(taskSnapshotReceived(snapshot));store.dispatch(pipelineSnackbarShown());
        Object.assign(window,{startTask:()=>store.dispatch(taskSnapshotReceived({...snapshot,revision:2,tasks:[...tasks,
            {...tasks[0],task_id:'new-task',status:'running',recording:{base_directory:'/test',recording_name:'Current recording',full_path:'/test/Current recording'},progress:{phase:'setting_up',progress_fraction:null,detail:'Preparing task'}}]}))});
        createRoot(document.getElementById('root')!).render(<Provider store={store}><MemoryRouter><Panel/></MemoryRouter></Provider>);
    `},bundle:true,write:false,outdir:'progress-panel-test',format:'esm',alias:{'@':path.resolve('src')},
        loader:{'.yaml':'text','.svg':'dataurl','.webp':'dataurl','.png':'dataurl','.woff':'dataurl','.woff2':'dataurl','.ttf':'dataurl'},
        external:['/images/*','../images/*','../assets/icons/import-icon.svg'],
        plugins:[{name:'host-boundary',setup(builder){
            builder.onResolve({filter:/^@\/services$/},()=>({path:'host',namespace:'host'}));
            builder.onLoad({filter:/.*/,namespace:'host'},()=>({contents:'export const useElectronIPC=()=>({api:null,isElectron:false}); export const serverUrls={};',loader:'ts'}));
        }}]});
    for(const file of bundle.outputFiles){
        if(file.path.endsWith('.css'))await page.addStyleTag({content:file.text});
        else await page.addScriptTag({content:file.text,type:'module'});
    }
    const panel=page.locator('.snackbar-main-container-modal');
    await expect(page.getByRole('button',{name:'Dismiss pipeline',exact:true})).toHaveCount(20);
    const bounds=(await panel.boundingBox())!;
    expect(bounds.y).toBeGreaterThanOrEqual(0);
    expect(bounds.height).toBeLessThanOrEqual(420);
    expect(await page.locator('.inner-content').evaluate(element=>element.scrollHeight>element.clientHeight)).toBe(true);
    await page.getByRole('button',{name:'Dismiss finished pipelines',exact:true}).click();
    await expect(page.getByRole('button',{name:'Dismiss pipeline',exact:true})).toHaveCount(0);
    await page.evaluate(()=>(window as unknown as {startTask:()=>void}).startTask());
    await expect(page.getByRole('button',{name:'Dismiss pipeline',exact:true})).toHaveCount(1);
    await expect(panel).toContainText('Current recording');
    await expect(page.getByRole('button',{name:'Stop all posthoc jobs',exact:true}).locator('.stop-alert-icon')).toHaveCount(1);
    await expect(page.getByRole('button',{name:'Close progress panel',exact:true})).toBeVisible();
    await page.screenshot({path:'test-results/progress-panel.png',animations:'disabled'});
});

