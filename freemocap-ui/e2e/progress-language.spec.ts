import {test,expect} from '@playwright/test';
import {build} from 'esbuild';
import path from 'node:path';
test('progress explains current work even with a percentage',async({page})=>{
await page.route('http://localhost:53117/',r=>r.fulfill({contentType:'text/html',body:'<div id="root"></div>'}));
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
        const detail='Reading 3 videos and detecting poses and ChArUco board points with RTMPose on CUDA GPU. Processed 3,324 of 3,324 camera images (3 videos x 1,108 frames each). This percentage is for detection only; 3D reconstruction and saving follow.';
        const tasks=[
          {task_id:'tracking',status:'running',progress:{phase:'collecting_camera_output',progress_fraction:1,detail}},
          {task_id:'reconstruction',status:'running',progress:{phase:'reconstructing',progress_fraction:null,detail:'Calculating skeleton positions and joint rotations. Also running: Drawing tracking overlays and saving annotated video 2. The recording is still processing.'}},
          {task_id:'finished',status:'complete',progress:{phase:'complete',progress_fraction:1,detail:'Processing complete. Motion-capture results have been saved to the recording folder.'}},
        ].map(task=>({...task,task_type:'mocap',revision:1,recording:{base_directory:'/test',recording_name:task.task_id,full_path:'/test/'+task.task_id},cameras:[],created_at:'2026-10-12T00:00:00Z',updated_at:'2026-10-12T00:01:00Z'}));
        store.dispatch(taskSnapshotReceived({server_instance_id:'20000000-0000-4000-8000-000000000003',revision:0,recording_owners:[],tasks:tasks.map(task=>({...task,status:"running",progress:{phase:"setting_up",progress_fraction:null,detail:"Preparing videos"}}))}));
        store.dispatch(taskSnapshotReceived({server_instance_id:'20000000-0000-4000-8000-000000000003',revision:1,recording_owners:[],tasks}));store.dispatch(pipelineSnackbarShown());
        createRoot(document.getElementById('root')!).render(<Provider store={store}><MemoryRouter><Panel/></MemoryRouter></Provider>);
    `},bundle:true,write:false,outdir:'progress-panel-test',format:'esm',alias:{'@':path.resolve('src')},
        loader:{'.yaml':'text','.svg':'dataurl','.webp':'dataurl','.png':'dataurl','.woff':'dataurl','.woff2':'dataurl','.ttf':'dataurl'},
        external:['/images/*','../images/*','../assets/icons/import-icon.svg'],
        plugins:[{name:'host-boundary',setup(builder){
            builder.onResolve({filter:/^@\/services$/},()=>({path:'host',namespace:'host'}));
            builder.onLoad({filter:/.*/,namespace:'host'},()=>({contents:'export const useElectronIPC=()=>({api:null,isElectron:false}); export const serverUrls={};',loader:'ts'}));
        }}]});

for(const f of bundle.outputFiles){if(f.path.endsWith('.css'))await page.addStyleTag({content:f.text});else await page.addScriptTag({content:f.text,type:'module'});}
const tracking=page.locator('.pipeline-group-card').filter({hasText:'Pipeline: tracking'});
await expect(tracking).toContainText('Reading 3 videos');
await expect(tracking).toContainText('percentage is for detection only');
await expect(tracking).toContainText('Running');
await expect(tracking).not.toContainText('Complete');
const reconstruction=page.locator('.pipeline-group-card').filter({hasText:'Pipeline: reconstruction'});
await expect(reconstruction).toContainText('joint rotations');
await expect(reconstruction).toContainText('annotated video 2');
const finished=page.locator('.pipeline-group-card').filter({hasText:'Pipeline: finished'});
await expect(finished).toContainText('Complete');
await expect(finished).toContainText('saved to the recording folder');
});
