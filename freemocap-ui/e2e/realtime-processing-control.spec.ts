import {test, expect} from '@playwright/test';
import {build} from 'esbuild';
import {resolve} from 'node:path';
import {readFile, readdir} from 'node:fs/promises';

test('processing details use real toolbar and production CSS without displacing the viewport', async ({page}, info) => {
    test.setTimeout(60000);
    page.on('pageerror', error => {throw error;});
    await page.route('**/*', route => route.fulfill({contentType:'text/html',body:'<div id="root"></div>'}));
    await page.setViewportSize({width:1920,height:1080}); await page.goto('https://processing-host.test/');
    const bundle = await build({stdin:{contents:`
        import React from 'react'; import {createRoot} from 'react-dom/client'; import {Provider} from 'react-redux';
        import './src/index.css'; import {store} from './src/store/store';
        import {ServerContext} from './src/services/server/server-context';
        import {StreamingViewPage} from './src/pages/StreamingViewPage';
        createRoot(document.getElementById('root')).render(<Provider store={store}><ServerContext.Provider value={{connectedCameraIds:[],isConnected:false,isFailed:false}}>
            <div style={{display:'flex',height:'100vh',paddingTop:48,boxSizing:'border-box'}}>
                <aside style={{width:300,flexShrink:0}}>Camera sidebar</aside>
                <main style={{display:'flex',flex:1,minWidth:0,height:'100%'}}><StreamingViewPage/></main>
            </div></ServerContext.Provider></Provider>);
    `,resolveDir:resolve('.'),loader:'tsx'},bundle:true,write:false,outdir:'processing-host',format:'esm',
        loader:{'.yaml':'text','.svg':'dataurl','.png':'dataurl','.webp':'dataurl','.woff2':'dataurl','.woff':'dataurl','.ttf':'dataurl'},
        alias:{'@':resolve('src')},external:['/images/*','/fonts/*','../images/splashmodal_art.webp','../assets/icons/import-icon.svg'],
        plugins:[{name:'hardware-and-status-fixtures',setup(builder){
            builder.onResolve({filter:/components\/(camera-views\/CameraViewsGrid|viewport3d\/ThreeJsCanvas)$/},args=>({path:args.path,namespace:'hardware'}));
            builder.onLoad({filter:/.*/,namespace:'hardware'},()=>({loader:'tsx',resolveDir:resolve('.'),contents:`import React from 'react';
                export function CameraViewsGrid(){return <div data-testid="camera-viewport" style={{height:'100%',background:'#111'}}>Camera preview</div>}
                export function ThreeJsCanvas(){return <div data-testid="three-viewport" style={{height:'100%',background:'#161616'}}>3D viewport</div>}`}));
            builder.onResolve({filter:/hooks\/useRealtimeStartup$/},args=>({path:args.path,namespace:'status'}));
            builder.onLoad({filter:/.*/,namespace:'status'},()=>({loader:'ts',contents:`
                export function useRealtimeStartup(){return {snapshot:{status:'failed',phase:'loading_models',elapsed_seconds:17,phase_elapsed_seconds:0,pipeline_id:'p',preview_ready:true,message:'Model unavailable'},pending:false,statusUnavailable:false,statusError:null,retry:()=>{window.retried=(window.retried||0)+1}}}`}));
        }}]});
    for(const output of bundle.outputFiles.filter(output=>output.path.endsWith('.css'))) await page.addStyleTag({content:output.text});
    const productionStyles=(await readdir(resolve('dist/assets'))).filter(name=>name.endsWith('.css'));
    expect(productionStyles.length).toBeGreaterThan(0);
    for(const filename of productionStyles) await page.addStyleTag({content:await readFile(resolve('dist/assets',filename),'utf8')});
    for(const output of bundle.outputFiles.filter(output=>!output.path.endsWith('.css'))) await page.addScriptTag({content:output.text,type:'module'});
    const trigger=page.getByRole('button',{name:'Processing status',exact:true});
    const panel=page.getByRole('dialog',{name:'Processing status',exact:true});
    await expect(trigger).toBeVisible(); await expect(panel).toHaveCount(0);
    await expect(page.getByText('Realtime processing is ready')).toHaveCount(0);
    const before=(await page.getByTestId('camera-viewport').boundingBox())!;
    expect(before.y).toBeLessThan(60); expect(before.height).toBeGreaterThan(1000);
    await page.screenshot({path:info.outputPath('processing-closed-wide.png')});
    await trigger.click(); await expect(panel).toBeVisible();
    expect(await page.getByTestId('camera-viewport').boundingBox()).toEqual(before);
    const prepare=panel.getByRole('button',{name:'Retry startup',exact:true});
    await expect(prepare).toBeVisible(); await expect(prepare).toBeInViewport();
    const colors=await prepare.evaluate(element=>{const style=getComputedStyle(element);return {fg:style.color,bg:style.backgroundColor,height:element.getBoundingClientRect().height};});
    expect(colors.fg).not.toBe('rgb(0, 0, 0)'); expect(colors.bg).not.toBe('rgba(0, 0, 0, 0)'); expect(colors.height).toBeGreaterThanOrEqual(30);
    const luminance=(color:string)=>color.match(/\d+/g)!.slice(0,3).map(Number).map(value=>{const linear=value/255;return linear<=.04045?linear/12.92:((linear+.055)/1.055)**2.4;}).reduce((sum,value,index)=>sum+value*[.2126,.7152,.0722][index],0);
    const contrast=(luminance(colors.fg)+.05)/(luminance(colors.bg)+.05);
    expect(contrast).toBeGreaterThanOrEqual(4.5);
    console.log(JSON.stringify({cameraBoundsBefore:before,cameraBoundsOpen:await page.getByTestId('camera-viewport').boundingBox(),button:colors,contrast}));
    await prepare.click(); expect(await page.evaluate(()=>(window as any).retried)).toBe(1);
    await page.screenshot({path:info.outputPath('processing-open-wide.png')});
    await page.keyboard.press('Escape'); await expect(panel).toHaveCount(0); await expect(trigger).toBeFocused();
    await page.setViewportSize({width:860,height:720}); await trigger.click(); await expect(prepare).toBeInViewport();
    const box=(await panel.boundingBox())!; expect(box.x).toBeGreaterThanOrEqual(12); expect(box.x+box.width).toBeLessThanOrEqual(848);
    await page.screenshot({path:info.outputPath('processing-open-compact.png')});
    await page.mouse.click(10,700); await expect(panel).toHaveCount(0);
});



test('existing websocket drives startup and Stop without recurring HTTP checks', async ({page}) => {
    test.setTimeout(60000);
    let gets=0, stops=0;
    let rejectStop:(()=>Promise<void>)|null=null;
    const startup=(status='running')=>({status,phase:status==='running'?'loading_models':'running',elapsed_seconds:4,phase_elapsed_seconds:2,pipeline_id:'p',message:null,error:null,delayed:false,preview_ready:true});
    await page.route('**/*',route=>{
        if(!route.request().url().includes('/freemocap/realtime/startup'))return route.fulfill({contentType:'text/html',body:'<div id="root"></div>'});
        if(route.request().method()==='POST'){
            stops++;if(stops===1){rejectStop=()=>route.fulfill({status:500,contentType:'application/json',body:JSON.stringify({detail:'Stop failed'})});return;}
            return route.fulfill({contentType:'application/json',body:JSON.stringify(startup('stopping'))});
        }
        gets++;return route.fulfill({contentType:'application/json',body:JSON.stringify(startup())});
    });
    await page.goto('https://startup-progress.test/');
    const bundle=await build({stdin:{contents:`
        import React from 'react';import {createRoot} from 'react-dom/client';import {Provider} from 'react-redux';import {configureStore} from '@reduxjs/toolkit';
        import './src/store';import {pipelinesSlice} from './src/store/slices/pipelines/pipelines-slice';
        import {connectionSlice,serverDisconnected,wsConnectionChanged,serverStateReceived} from './src/store/slices/connection/connection-slice';
        import {realtimeSlice} from './src/store/slices/realtime/realtime-slice';
        import {applyTaskSnapshot} from './src/services/server/task-progress';import {TransportService} from './src/services/server/transport/TransportService';
        import {CURRENT_VERSION} from './src/services/server/transport/message-contract';import {encode} from 'cbor-x';
        import {RealtimeStartupBanner} from './src/components/common/RealtimeStartupBanner';
        const store=configureStore({reducer:{connection:connectionSlice.reducer,pipelines:pipelinesSlice.reducer,realtime:realtimeSlice.reducer},preloadedState:{connection:{...connectionSlice.getInitialState(),isConnected:true,serverPid:1},realtime:{...realtimeSlice.getInitialState(),isConnected:true}}});
        let receive;const socket={readyState:0,binaryType:'',set onmessage(callback){receive=callback},close(){},send(){}};
        const transport=new TransportService({url:'ws://fake.invalid',socketFactory:()=>socket});
        transport.subscribeToProgress(message=>applyTaskSnapshot(message.snapshot,store.getState().pipelines,store.dispatch));
        transport.subscribeToProtocolErrors(error=>{throw error;});transport.connect();
        window.pushProgress=snapshot=>{const bytes=encode({kind:'progress',version:CURRENT_VERSION,timestamp:1,sequence:snapshot.revision,snapshot});receive({data:bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength)});};
        window.disconnect=()=>store.dispatch(serverDisconnected());window.reconnect=()=>{store.dispatch(wsConnectionChanged(true));store.dispatch(serverStateReceived({server_pid:1,state:{camera_groups:{},realtime_pipelines:[{id:'p',alive:true,camera_group_id:'g',camera_ids:[]}]}}));};
        createRoot(document.getElementById('root')).render(<Provider store={store}><RealtimeStartupBanner/></Provider>);
    `,loader:'tsx',resolveDir:resolve('.')},bundle:true,write:false,outdir:'startup-browser',format:'esm',alias:{'@':resolve('src')},loader:{'.yaml':'text'},logLevel:'silent'});
    for(const output of bundle.outputFiles.filter(output=>output.path.endsWith('.css')))await page.addStyleTag({content:output.text});
    for(const output of bundle.outputFiles.filter(output=>output.path.endsWith('.js')))await page.addScriptTag({content:output.text,type:'module'});
    const trigger=page.getByRole('button',{name:'Processing status',exact:true});await expect(trigger).toBeVisible();await expect.poll(()=>gets).toBe(1);
    await page.waitForTimeout(1100);expect(gets).toBe(1);await trigger.click();
    let revision=1;
    const task={task_id:'startup:1',revision:1,task_type:'realtime_startup',recording:null,status:'running',progress:{phase:'loading_models',detail:'progress',progress_fraction:null},result:startup(),cameras:[],operations:[],timing:null,created_at:'2026-11-02T10:00:00Z',updated_at:'2026-11-02T10:00:00Z'};
    const push=()=>page.evaluate(snapshot=>(window as any).pushProgress(snapshot),{server_instance_id:'00000000-0000-4000-8000-000000000001',revision:revision++,recording_owners:[],tasks:[task]});
    await push();await page.getByRole('button',{name:'Stop startup',exact:true}).click();expect(stops).toBe(1);
    task.revision++;await push();await rejectStop!();await expect(page.getByText(/Stop request was not confirmed/)).toBeVisible();
    await page.getByRole('button',{name:'Stop startup',exact:true}).click();expect(stops).toBe(2);
    await expect(page.getByText('Stopping realtime startup',{exact:true})).toBeVisible();await push();
    await expect(page.getByText('Stopping realtime startup',{exact:true})).toBeVisible();await page.waitForTimeout(1100);expect(gets).toBe(1);
    await page.keyboard.press('Escape');task.revision++;task.status='cancelled';task.result=startup('stopped');await push();
    await page.waitForTimeout(1100);expect(gets).toBe(1);await trigger.click();await expect(page.getByRole('button',{name:'Retry startup',exact:true})).toBeVisible();
    await page.keyboard.press('Escape');await page.evaluate(()=>(window as any).disconnect());await page.evaluate(()=>(window as any).reconnect());
    await expect.poll(()=>gets).toBe(2);await push();await trigger.click();await expect(page.getByRole('button',{name:'Retry startup',exact:true})).toBeVisible();
    await page.waitForTimeout(1100);expect(gets).toBe(2);console.log(JSON.stringify({gets,stops,transport:'CBOR -> TransportService -> applyTaskSnapshot -> startup controls'}));
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
