import {test, expect} from '@playwright/test';
import {build} from 'esbuild';
import {resolve} from 'node:path';
import {readFile, readdir} from 'node:fs/promises';

test('one themed realtime button shows stages, cancel, retry and errors in the real toolbar', async ({page},info) => {
    test.setTimeout(60000);page.on('pageerror',error=>{throw error;});
    await page.route('**/*',route=>route.fulfill({contentType:'text/html',body:'<div id="root"></div>'}));
    await page.setViewportSize({width:1255,height:900});await page.goto('https://realtime-toolbar.test/');
    const bundle=await build({stdin:{contents:`
        import React from 'react';import {createRoot} from 'react-dom/client';import {Provider} from 'react-redux';import './src/index.css';
        import {store} from './src/store/store';import {ServerContext} from './src/services/server/server-context';import {StreamingViewPage} from './src/pages/StreamingViewPage';
        import {OperationErrorBanner} from './src/components/common/OperationErrorBanner';import {serverStateReceived} from './src/store/slices/connection/connection-slice';
        window.connected=alive=>store.dispatch(serverStateReceived({server_pid:1,state:{camera_groups:{},realtime_pipelines:alive?[{id:'p',alive:true,camera_group_id:'g',camera_ids:[]}]:[]}}));
        window.applyFailure=()=>store.dispatch({type:'realtime/apply/rejected',error:{message:'Could not start processing'},meta:{arg:store.getState().realtime.pipelineConfig}});
        createRoot(document.getElementById('root')).render(<Provider store={store}><ServerContext.Provider value={{connectedCameraIds:[],isConnected:false,isFailed:false}}>
        <div style={{display:'flex',height:'100vh',paddingTop:48,boxSizing:'border-box'}}><aside style={{width:300,flexShrink:0}}>Camera sidebar</aside>
        <main style={{display:'flex',flexDirection:'column',flex:1,minWidth:0,height:'100%'}}><OperationErrorBanner/><StreamingViewPage/></main></div>
        </ServerContext.Provider></Provider>);
    `,resolveDir:resolve('.'),loader:'tsx'},bundle:true,write:false,outdir:'realtime-button-host',format:'esm',
        loader:{'.yaml':'text','.svg':'dataurl','.png':'dataurl','.webp':'dataurl','.woff2':'dataurl','.woff':'dataurl','.ttf':'dataurl'},alias:{'@':resolve('src')},external:['/images/*','/fonts/*','../images/splashmodal_art.webp','../assets/icons/import-icon.svg'],
        plugins:[{name:'hardware-and-status',setup(builder){
            builder.onResolve({filter:/components\/(camera-views\/CameraViewsGrid|viewport3d\/ThreeJsCanvas)$/},args=>({path:args.path,namespace:'hardware'}));
            builder.onLoad({filter:/.*/,namespace:'hardware'},()=>({loader:'tsx',resolveDir:resolve('.'),contents:`import React from 'react';export function CameraViewsGrid(){return <div data-testid="camera-viewport" style={{height:'100%',background:'#111'}}>Camera preview</div>}export function ThreeJsCanvas(){return <div style={{height:'100%',background:'#161616'}}>3D viewport</div>}`}));
            builder.onResolve({filter:/hooks\/useRealtimeStartup$/},args=>({path:args.path,namespace:'status'}));
            builder.onLoad({filter:/.*/,namespace:'status'},()=>({loader:'ts',resolveDir:resolve('.'),contents:`import {useState} from 'react';export function useRealtimeStartup(){const[state,setState]=useState({snapshot:null,pending:false,operationId:'start:1',statusError:null});window.setStartup=setState;return {...state,stop:()=>{window.stops=(window.stops||0)+1},retry:()=>{window.retries=(window.retries||0)+1}}}`}));
        }}]});
    for(const output of bundle.outputFiles.filter(output=>output.path.endsWith('.css')))await page.addStyleTag({content:output.text});
    for(const name of (await readdir(resolve('dist/assets'))).filter(name=>name.endsWith('.css')))await page.addStyleTag({content:await readFile(resolve('dist/assets',name),'utf8')});
    for(const output of bundle.outputFiles.filter(output=>!output.path.endsWith('.css')))await page.addScriptTag({content:output.text,type:'module'});
    const update=(status:string,phase='running',error:string|null=null)=>page.evaluate(value=>(window as any).setStartup({snapshot:{status:value.status,phase:value.phase,error:value.error},pending:false,operationId:'start:1',statusError:null}),{status,phase,error});
    const idle=page.getByRole('button',{name:'Start realtime processing',exact:true});await expect(idle).toHaveText('Realtime processing');
    await page.evaluate(()=>(window as any).applyFailure());await expect(page.getByRole('alert')).toContainText('Could not start processing');await expect(idle).toBeEnabled();await page.getByRole('button',{name:'Dismiss',exact:true}).click();
    await expect(page.getByRole('dialog')).toHaveCount(0);await expect(page.locator('.realtime-processing-popover')).toHaveCount(0);
    const before=await page.getByTestId('camera-viewport').boundingBox();
    await page.evaluate(()=>(window as any).connected(true));
    for(const [phase,label] of [['starting_cameras','Starting cameras'],['loading_models','Loading tracking'],['warming_models','Warming tracking'],['waiting_for_frames','Waiting for frames']]){
        await update('running',phase);const control=page.getByRole('button',{name:`Stop realtime startup: ${label}`,exact:true});await expect(control).toHaveText(label);await expect(control).toBeEnabled();
        await expect(control.locator('.loader-icon')).toHaveCSS('animation-name','spin-ramp');expect(await page.getByTestId('camera-viewport').boundingBox()).toEqual(before);
    }
    await page.getByRole('button',{name:'Stop realtime startup: Waiting for frames',exact:true}).click();expect(await page.evaluate(()=>(window as any).stops)).toBe(1);
    await update('stopping');await expect(page.getByRole('button',{name:'Stopping realtime processing',exact:true})).toBeDisabled();
    await update('ready');const running=page.getByRole('button',{name:'Stop realtime processing',exact:true});await expect(running).toHaveText('Realtime processing');
    await expect(running).toHaveAttribute('aria-pressed','true');await expect(running.locator('.live-active-icon')).toBeVisible();
    const color=await running.locator('p').evaluate(element=>getComputedStyle(element).color);expect(color).toBe('rgb(22, 221, 18)');
    await page.screenshot({path:info.outputPath('realtime-running-1255.png')});
    await update('failed','loading_models','Tracking model could not load');const retry=page.getByRole('button',{name:'Retry realtime processing',exact:true});await expect(retry).toBeEnabled();
    await expect(page.getByRole('alert')).toContainText('Tracking model could not load');await page.getByRole('button',{name:'Dismiss',exact:true}).click();await update('failed','loading_models','Tracking model could not load');await expect(page.getByRole('alert')).toHaveCount(0);
    await retry.click();expect(await page.evaluate(()=>(window as any).retries)).toBe(1);
    for(const width of [1255,860]){
        await page.setViewportSize({width,height:720});await update('running','loading_models');const control=page.getByRole('button',{name:'Stop realtime startup: Loading tracking',exact:true});await expect(control).toBeInViewport();
        const box=(await control.boundingBox())!, outputs=(await page.getByRole('button',{name:'Streaming outputs',exact:true}).boundingBox())!;
        expect(box.x).toBeGreaterThanOrEqual(300);expect(outputs.x-(box.x+box.width)).toBeGreaterThanOrEqual(12);expect(outputs.x+outputs.width).toBeLessThan(width);
        await expect(control).toHaveCSS('border-top-width','1px');await expect(control).toHaveCSS('border-top-style','solid');await expect(control).toHaveCSS('border-top-color','rgb(110, 110, 110)');
        await page.screenshot({path:info.outputPath(`realtime-loading-${width}.png`)});console.log(JSON.stringify({width,button:box,outputs,runningTextColor:color}));
    }
});

test('websocket startup and same-button Stop work without recurring HTTP checks', async ({page}) => {
    test.setTimeout(60000);let gets=0,stops=0;
    const status=(value='running')=>({status:value,phase:'loading_models',elapsed_seconds:1,phase_elapsed_seconds:1,pipeline_id:'p',error:null,message:null});
    await page.route('**/*',route=>{if(!route.request().url().includes('/freemocap/realtime/startup'))return route.fulfill({contentType:'text/html',body:'<div id="root"></div>'});if(route.request().method()==='POST'){stops++;return route.fulfill({contentType:'application/json',body:JSON.stringify(status('stopping'))});}gets++;return route.fulfill({contentType:'application/json',body:JSON.stringify(status())});});
    await page.goto('https://startup-control.test/');
    const bundle=await build({stdin:{contents:`
        import React from 'react';import {createRoot} from 'react-dom/client';import {Provider} from 'react-redux';import {configureStore} from '@reduxjs/toolkit';import './src/store';
        import {pipelinesSlice} from './src/store/slices/pipelines/pipelines-slice';import {connectionSlice} from './src/store/slices/connection/connection-slice';import {realtimeSlice} from './src/store/slices/realtime/realtime-slice';
        import {applyTaskSnapshot} from './src/services/server/task-progress';import {TransportService} from './src/services/server/transport/TransportService';import {CURRENT_VERSION} from './src/services/server/transport/message-contract';import {encode} from 'cbor-x';
        import {RealtimeProcessingButton} from './src/components/control-panels/realtime-panel/RealtimeProcessingButton';
        const store=configureStore({reducer:{connection:connectionSlice.reducer,pipelines:pipelinesSlice.reducer,realtime:realtimeSlice.reducer},preloadedState:{connection:{...connectionSlice.getInitialState(),isConnected:true,serverPid:1}}});
        let receive;const transport=new TransportService({url:'ws://fake.invalid',socketFactory:()=>({readyState:0,binaryType:'',set onmessage(callback){receive=callback},close(){},send(){}})});
        transport.subscribeToProgress(message=>applyTaskSnapshot(message.snapshot,store.getState().pipelines,store.dispatch));transport.connect();
        window.progress=snapshot=>{const bytes=encode({kind:'progress',version:CURRENT_VERSION,timestamp:1,sequence:1,snapshot});receive({data:bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength)});};
        createRoot(document.getElementById('root')).render(<Provider store={store}><RealtimeProcessingButton connected={true} loading={false} onToggle={()=>{}}/></Provider>);
    `,resolveDir:resolve('.'),loader:'tsx'},bundle:true,write:false,format:'esm',alias:{'@':resolve('src')},loader:{'.yaml':'text'},logLevel:'silent'});
    await page.addScriptTag({content:bundle.outputFiles[0].text,type:'module'});const control=page.getByRole('button',{name:'Stop realtime startup: Loading tracking',exact:true});await expect(control).toBeVisible();
    await page.waitForTimeout(1100);expect(gets).toBe(1);await control.click();expect(stops).toBe(1);await expect(page.getByRole('button',{name:'Stopping realtime processing',exact:true})).toBeDisabled();
    await page.evaluate(snapshot=>(window as any).progress(snapshot),{server_instance_id:'00000000-0000-4000-8000-000000000001',revision:1,recording_owners:[],tasks:[{task_id:'startup:1',revision:1,task_type:'realtime_startup',recording:null,status:'cancelled',progress:{phase:'stopped',detail:'',progress_fraction:null},result:status('stopped'),cameras:[],created_at:'2026-11-02T10:00:00Z',updated_at:'2026-11-02T10:00:00Z'}]});
    await expect(page.getByRole('button',{name:'Retry realtime processing',exact:true})).toBeEnabled();await page.waitForTimeout(1100);expect(gets).toBe(1);expect(stops).toBe(1);await expect(page.getByRole('dialog')).toHaveCount(0);
});

test('late startup reads cannot replace pushed progress or survive server change and unmount', async ({page}) => {
    test.setTimeout(60000);let reads=0;const held:{release:(status:string)=>Promise<void>}[]=[];
    await page.route('**/*',route=>{
        if(!route.request().url().includes('/freemocap/realtime/startup'))return route.fulfill({contentType:'text/html',body:'<div id="root"></div>'});
        reads++;held.push({release:async status=>{await route.fulfill({contentType:'application/json',body:JSON.stringify({status,phase:'loading_models',elapsed_seconds:1,phase_elapsed_seconds:1,pipeline_id:'p',message:null,error:null,delayed:false,preview_ready:false})}).catch(()=>{});}});
    });
    await page.goto('https://late-startup.test/');
    const bundle=await build({stdin:{contents:`
        import React from 'react';import {createRoot} from 'react-dom/client';import {Provider} from 'react-redux';import {configureStore} from '@reduxjs/toolkit';
        import './src/store';import {pipelinesSlice,taskSnapshotReceived} from './src/store/slices/pipelines/pipelines-slice';
        import {connectionSlice,serverDisconnected,wsConnectionChanged,serverStateReceived} from './src/store/slices/connection/connection-slice';
        import {realtimeSlice} from './src/store/slices/realtime/realtime-slice';import {useRealtimeStartup} from './src/hooks/useRealtimeStartup';
        const store=configureStore({reducer:{pipelines:pipelinesSlice.reducer,connection:connectionSlice.reducer,realtime:realtimeSlice.reducer},preloadedState:{connection:{...connectionSlice.getInitialState(),isConnected:true,serverPid:1}}});
        window.pushTask=()=>store.dispatch(taskSnapshotReceived({server_instance_id:'00000000-0000-4000-8000-000000000001',revision:1,recording_owners:[],tasks:[{task_id:'startup:1',revision:1,task_type:'realtime_startup',status:'running',recording:null,progress:{phase:'loading_models',detail:'',progress_fraction:null},result:{status:'running',phase:'loading_models',elapsed_seconds:2,phase_elapsed_seconds:2,pipeline_id:'p',message:null,error:null,preview_ready:false,delayed:false},cameras:[],operations:[],timing:null,created_at:'2026-11-02T10:00:00Z',updated_at:'2026-11-02T10:00:00Z'}]}));
        let pid=1;function change(){store.dispatch(serverDisconnected());store.dispatch(wsConnectionChanged(true));store.dispatch(serverStateReceived({server_pid:++pid,state:{camera_groups:{},realtime_pipelines:[]}}));}
        function Details(){const state=useRealtimeStartup();return <output>{state.snapshot?.status??'none'}</output>}
        function App(){const[mounted,setMounted]=React.useState(true);return <Provider store={store}><button onClick={change}>Change server</button><button onClick={()=>setMounted(false)}>Unmount</button>{mounted&&<Details/>}</Provider>}
        createRoot(document.getElementById('root')).render(<App/>);
    `,loader:'tsx',resolveDir:resolve('.')},bundle:true,write:false,format:'esm',alias:{'@':resolve('src')},loader:{'.yaml':'text'},logLevel:'silent'});
    await page.addScriptTag({content:bundle.outputFiles[0].text,type:'module'});await expect.poll(()=>reads).toBe(1);
    await page.evaluate(()=>(window as any).pushTask());await expect(page.locator('output')).toHaveText('running');await held[0].release('idle');
    await page.waitForTimeout(650);await expect(page.locator('output')).toHaveText('running');expect(reads).toBe(1);
    await page.getByText('Change server',{exact:true}).click();await expect.poll(()=>reads).toBe(2);
    await page.getByText('Change server',{exact:true}).click();await expect.poll(()=>reads).toBe(3);
    await held[2].release('idle');await expect(page.locator('output')).toHaveText('idle');await held[1].release('running');
    await page.waitForTimeout(650);await expect(page.locator('output')).toHaveText('idle');expect(reads).toBe(3);
    await page.getByText('Change server',{exact:true}).click();await expect.poll(()=>reads).toBe(4);await page.getByText('Unmount',{exact:true}).click();await held[3].release('running');
    await page.waitForTimeout(650);expect(reads).toBe(4);await expect(page.locator('output')).toHaveCount(0);
});
