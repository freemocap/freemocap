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
            builder.onResolve({filter:/hooks\/use(RealtimeStartup|OnnxPreparation)$/},args=>({path:args.path,namespace:'status'}));
            builder.onLoad({filter:/.*/,namespace:'status'},args=>({loader:'ts',contents:args.path.endsWith('useRealtimeStartup') ? `
                export function useRealtimeStartup(){return {snapshot:{status:'ready',phase:'running',elapsed_seconds:17,phase_elapsed_seconds:0,pipeline_id:'p',preview_ready:true,message:'Live frames are streaming'},pending:false,statusUnavailable:false,statusError:null}}`
                : `export function useOnnxPreparation(){return {snapshot:{pipeline_id:'p',status:'idle',phase:'idle',elapsed_seconds:0,model_name:null,message:'Using CUDA',error:null,can_prepare:true,can_cancel:false,requested_provider:null,active_provider:'cuda'},onPrepare:()=>{window.prepared=(window.prepared||0)+1}}}`}));
        }}]});
    for(const output of bundle.outputFiles.filter(output=>output.path.endsWith('.css'))) await page.addStyleTag({content:output.text});
    const productionStyles=(await readdir(resolve('dist/assets'))).filter(name=>name.endsWith('.css'));
    expect(productionStyles.length).toBeGreaterThan(0);
    for(const filename of productionStyles) await page.addStyleTag({content:await readFile(resolve('dist/assets',filename),'utf8')});
    for(const output of bundle.outputFiles.filter(output=>!output.path.endsWith('.css'))) await page.addScriptTag({content:output.text,type:'module'});
    const trigger=page.getByRole('button',{name:'Processing and acceleration',exact:true});
    const panel=page.getByRole('dialog',{name:'Processing and acceleration',exact:true});
    await expect(trigger).toBeVisible(); await expect(panel).toHaveCount(0);
    await expect(page.getByText('Realtime processing is ready')).toHaveCount(0);
    const before=(await page.getByTestId('camera-viewport').boundingBox())!;
    expect(before.y).toBeLessThan(60); expect(before.height).toBeGreaterThan(1000);
    await page.screenshot({path:info.outputPath('processing-closed-wide.png')});
    await trigger.click(); await expect(panel).toBeVisible();
    expect(await page.getByTestId('camera-viewport').boundingBox()).toEqual(before);
    const prepare=panel.getByRole('button',{name:'Prepare TensorRT',exact:true});
    await expect(prepare).toBeVisible(); await expect(prepare).toBeInViewport();
    const colors=await prepare.evaluate(element=>{const style=getComputedStyle(element);return {fg:style.color,bg:style.backgroundColor,height:element.getBoundingClientRect().height};});
    expect(colors.fg).not.toBe('rgb(0, 0, 0)'); expect(colors.bg).not.toBe('rgba(0, 0, 0, 0)'); expect(colors.height).toBeGreaterThanOrEqual(30);
    const luminance=(color:string)=>color.match(/\d+/g)!.slice(0,3).map(Number).map(value=>{const linear=value/255;return linear<=.04045?linear/12.92:((linear+.055)/1.055)**2.4;}).reduce((sum,value,index)=>sum+value*[.2126,.7152,.0722][index],0);
    const contrast=(luminance(colors.fg)+.05)/(luminance(colors.bg)+.05);
    expect(contrast).toBeGreaterThanOrEqual(4.5);
    console.log(JSON.stringify({cameraBoundsBefore:before,cameraBoundsOpen:await page.getByTestId('camera-viewport').boundingBox(),button:colors,contrast}));
    await prepare.click(); expect(await page.evaluate(()=>(window as any).prepared)).toBe(1);
    await page.screenshot({path:info.outputPath('processing-open-wide.png')});
    await page.keyboard.press('Escape'); await expect(panel).toHaveCount(0); await expect(trigger).toBeFocused();
    await page.setViewportSize({width:860,height:720}); await trigger.click(); await expect(prepare).toBeInViewport();
    const box=(await panel.boundingBox())!; expect(box.x).toBeGreaterThanOrEqual(12); expect(box.x+box.width).toBeLessThanOrEqual(848);
    await page.screenshot({path:info.outputPath('processing-open-compact.png')});
    await page.mouse.click(10,700); await expect(panel).toHaveCount(0);
});


test('existing websocket progress drives actual processing controls with no recurring HTTP checks', async ({page}) => {
    test.setTimeout(60000);
    let startupGets=0, prepGets=0, prepPosts=0, stopPosts=0, startupStops=0;
    let rejectStop: (()=>Promise<void>) | null=null;
    const startup=(status='running')=>({status,phase:status==='running'?'loading_models':'running',elapsed_seconds:4,phase_elapsed_seconds:2,pipeline_id:'p',message:null,error:null,delayed:false,preview_ready:true});
    const preparation=(status='idle')=>({pipeline_id:'p',status,phase:status,elapsed_seconds:3,model_name:null,message:null,error:null,can_prepare:status==='idle'||status==='cancelled',can_cancel:status==='running'||status==='queued',requested_provider:'trt',active_provider:'cuda'});
    await page.route('**/*', route => {
        const url=route.request().url(), post=route.request().method()==='POST';
        let body: unknown;
        if(url.includes('/freemocap/realtime/startup')) {if(post){startupStops++;body=startup('stopping');}else{startupGets++;body=startup();}}
        else if(url.includes('/freemocap/onnx/preparation/')) {
            if(post && url.endsWith('/stop')){
                stopPosts++;
                if(stopPosts===1){rejectStop=()=>route.fulfill({status:500,contentType:'application/json',body:JSON.stringify({detail:'Worker stop failed'})});return;}
                body=preparation('stopping');
            }
            else if(post){prepPosts++;body=preparation('queued');}
            else {prepGets++;body=preparation(prepGets===1?'unavailable':'idle');}
        } else return route.fulfill({contentType:'text/html',body:'<div id="root"></div>'});
        return route.fulfill({contentType:'application/json',body:JSON.stringify(body)});
    });
    await page.goto('https://progress-hook.test/');
    const bundle=await build({stdin:{contents:`
        import React from 'react'; import {createRoot} from 'react-dom/client'; import {Provider} from 'react-redux'; import {configureStore} from '@reduxjs/toolkit';
        import './src/store';
        import {pipelinesSlice} from './src/store/slices/pipelines/pipelines-slice';
        import {connectionSlice,serverDisconnected,wsConnectionChanged,serverStateReceived} from './src/store/slices/connection/connection-slice';
        import {realtimeSlice} from './src/store/slices/realtime/realtime-slice';
        import {applyTaskSnapshot} from './src/services/server/task-progress';
        import {TransportService} from './src/services/server/transport/TransportService';
        import {CURRENT_VERSION} from './src/services/server/transport/message-contract';
        import {encode} from 'cbor-x';
        import {RealtimeStartupBanner} from './src/components/common/RealtimeStartupBanner';
        const store=configureStore({reducer:{connection:connectionSlice.reducer,pipelines:pipelinesSlice.reducer,realtime:realtimeSlice.reducer},preloadedState:{connection:{...connectionSlice.getInitialState(),isConnected:true,serverPid:1},realtime:{...realtimeSlice.getInitialState(),isConnected:true}}});
        let receive;const socket={readyState:0,binaryType:'',set onmessage(callback){receive=callback},close(){},send(){}};
        const transport=new TransportService({url:'ws://fake.invalid',socketFactory:()=>socket});
        transport.subscribeToProgress(message=>applyTaskSnapshot(message.snapshot,store.getState().pipelines,store.dispatch));
        transport.subscribeToProtocolErrors(error=>{throw error;});transport.connect();
        window.pushProgress=snapshot=>{const bytes=encode({kind:'progress',version:CURRENT_VERSION,timestamp:1,sequence:snapshot.revision,snapshot});receive({data:bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength)});};
        window.disconnect=()=>store.dispatch(serverDisconnected()); window.reconnect=()=>{store.dispatch(wsConnectionChanged(true));store.dispatch(serverStateReceived({server_pid:1,state:{camera_groups:{},realtime_pipelines:[{id:'p',alive:true,camera_group_id:'g',camera_ids:[]}]}}));};
        createRoot(document.getElementById('root')).render(<Provider store={store}><RealtimeStartupBanner/></Provider>);
    `,loader:'tsx',resolveDir:resolve('.')},bundle:true,write:false,outdir:'progress-browser',format:'esm',alias:{'@':resolve('src')},loader:{'.yaml':'text'},logLevel:'silent'});
    for(const output of bundle.outputFiles.filter(output=>output.path.endsWith('.css'))) await page.addStyleTag({content:output.text});
    for(const output of bundle.outputFiles.filter(output=>output.path.endsWith('.js'))) await page.addScriptTag({content:output.text,type:'module'});
    const trigger=page.getByRole('button',{name:'Processing and acceleration',exact:true});
    await expect(trigger).toBeVisible(); await expect.poll(()=>startupGets).toBe(1);
    await page.waitForTimeout(1100); expect(startupGets).toBe(1); expect(prepGets).toBe(0);
    await trigger.click(); await expect.poll(()=>prepGets).toBe(1);
    await page.waitForTimeout(1100); expect(prepGets).toBe(1);
    let revision=1;
    const tasks: any[]=[];
    const task=(id:string,type:string,result:any,created='2026-11-02T10:00:00Z')=>({task_id:id,revision:1,task_type:type,recording:null,status:'running',progress:{phase:result.phase,detail:'progress',progress_fraction:null},result,cameras:[],operations:[],timing:null,created_at:created,updated_at:created});
    const push=async()=>page.evaluate(snapshot=>(window as any).pushProgress(snapshot),{server_instance_id:'00000000-0000-4000-8000-000000000001',revision:revision++,recording_owners:[],tasks});
    tasks.push(task('startup:1','realtime_startup',startup('ready')));await push();
    await expect(page.getByRole('button',{name:'Prepare TensorRT',exact:true})).toBeVisible();
    expect(prepGets).toBe(2); // One capability refresh on the semantic ready event.
    await page.getByRole('button',{name:'Prepare TensorRT',exact:true}).click();expect(prepPosts).toBe(1);
    tasks.push(task('prep:1','onnx_preparation',preparation('running'),'2026-11-02T10:01:00Z'));await push();
    await expect(page.getByText('Preparing TensorRT',{exact:true})).toBeVisible();
    await page.waitForTimeout(1100);expect(prepGets).toBe(2);expect(startupGets).toBe(1);
    await page.getByRole('button',{name:'Stop preparation; keep CUDA',exact:true}).click();expect(stopPosts).toBe(1);
    tasks[1]={...tasks[1],revision:2};await push();
    await rejectStop!();await expect(page.getByText(/Stop request was not confirmed/)).toBeVisible();
    await page.getByRole('button',{name:'Stop preparation; keep CUDA',exact:true}).click();expect(stopPosts).toBe(2);
    await expect(page.getByText('Stopping TensorRT preparation',{exact:true})).toBeVisible();
    await push(); // Unrelated registry revision must not overwrite command response.
    await expect(page.getByText('Stopping TensorRT preparation',{exact:true})).toBeVisible();
    tasks[1]={...tasks[1],revision:2,result:preparation('stopping')};await push();
    await page.waitForTimeout(1100);expect(prepGets).toBe(2);
    await page.keyboard.press('Escape');
    tasks[1]={...tasks[1],revision:3,status:'cancelled',result:preparation('cancelled')};await push();
    await page.waitForTimeout(1100);expect(prepGets).toBe(2);
    await trigger.click();await expect(page.getByRole('button',{name:'Retry TensorRT preparation',exact:true})).toBeVisible();
    await page.waitForTimeout(1100);expect(prepGets).toBe(2);await page.keyboard.press('Escape');
    await page.evaluate(()=>(window as any).disconnect());await page.evaluate(()=>(window as any).reconnect());
    await expect.poll(()=>startupGets).toBe(2);await push();
    await trigger.click();await expect(page.getByRole('button',{name:'Retry TensorRT preparation',exact:true})).toBeVisible();
    await page.waitForTimeout(1100);expect(prepGets).toBe(2);expect(startupGets).toBe(2);
    tasks.push(task('startup:2','realtime_startup',startup(),'2026-11-02T10:02:00Z'));await push();
    await page.getByRole('button',{name:'Stop startup',exact:true}).click();expect(startupStops).toBe(1);
    await expect(page.getByText('Stopping realtime startup',{exact:true})).toBeVisible();
    await page.waitForTimeout(1100);expect(startupGets).toBe(2);expect(prepGets).toBe(2);
    console.log(JSON.stringify({startupGets,prepGets,prepPosts,stopPosts,startupStops,transport:'real CBOR TransportService -> applyTaskSnapshot -> store -> controls'}));
});

test('late initial snapshots cannot replace pushed progress or survive close, server change and unmount', async ({page}) => {
    test.setTimeout(60000);
    const held: {release:(status:string)=>Promise<void>}[]=[];
    let reads=0;
    await page.route('**/*', route=>{
        if(!route.request().url().includes('/freemocap/onnx/preparation/')) return route.fulfill({contentType:'text/html',body:'<div id="root"></div>'});
        reads++;
        const pipeline_id=route.request().url().split('/').at(-1);
        held.push({release:async status=>{await route.fulfill({contentType:'application/json',body:JSON.stringify({pipeline_id,status,phase:status,elapsed_seconds:1,model_name:null,message:null,error:null,can_prepare:true,can_cancel:false,requested_provider:'trt',active_provider:'cuda'})}).catch(()=>{});}});
    });
    await page.goto('https://late-progress.test/');
    const bundle=await build({stdin:{contents:`
        import React from 'react';import {createRoot} from 'react-dom/client';import {Provider} from 'react-redux';import {configureStore} from '@reduxjs/toolkit';
        import './src/store';import {pipelinesSlice,taskSnapshotReceived} from './src/store/slices/pipelines/pipelines-slice';
        import {useOnnxPreparation} from './src/hooks/useOnnxPreparation';
        const store=configureStore({reducer:{pipelines:pipelinesSlice.reducer,connection:(state={isConnected:true,serverPid:1},action)=>action.type==='server'?{...state,serverPid:state.serverPid+1}:state}});
        window.pushTask=()=>store.dispatch(taskSnapshotReceived({server_instance_id:'00000000-0000-4000-8000-000000000001',revision:1,recording_owners:[],tasks:[{task_id:'prep:1',revision:1,task_type:'onnx_preparation',status:'running',recording:null,progress:{phase:'running',detail:'',progress_fraction:null},result:{pipeline_id:'p1',status:'running',phase:'running',elapsed_seconds:2,model_name:null,message:null,error:null,can_prepare:false,can_cancel:true,requested_provider:'trt',active_provider:'cuda'},cameras:[],operations:[],timing:null,created_at:'2026-11-02T10:00:00Z',updated_at:'2026-11-02T10:00:00Z'}]}));
        function Details({pipeline,open}){const state=useOnnxPreparation('p'+pipeline,open);return <output>{state.snapshot?.status??'none'}</output>}
        function App(){const[pipeline,setPipeline]=React.useState(1),[open,setOpen]=React.useState(true),[mounted,setMounted]=React.useState(true);return <Provider store={store}><button onClick={()=>setPipeline(value=>value+1)}>Next pipeline</button><button onClick={()=>setOpen(!open)}>Toggle details</button><button onClick={()=>store.dispatch({type:'server'})}>Change server</button><button onClick={()=>setMounted(false)}>Unmount</button>{mounted&&<Details pipeline={pipeline} open={open}/>}</Provider>}
        createRoot(document.getElementById('root')).render(<App/>);
    `,loader:'tsx',resolveDir:resolve('.')},bundle:true,write:false,format:'esm',alias:{'@':resolve('src')},loader:{'.yaml':'text'},logLevel:'silent'});
    await page.addScriptTag({content:bundle.outputFiles[0].text,type:'module'});
    await expect.poll(()=>reads).toBe(1);await page.evaluate(()=>(window as any).pushTask());
    await expect(page.locator('output')).toHaveText('running');await held[0].release('idle');
    await page.waitForTimeout(650);await expect(page.locator('output')).toHaveText('running');expect(reads).toBe(1);
    await page.getByText('Next pipeline',{exact:true}).click();await expect.poll(()=>reads).toBe(2);
    await page.getByText('Toggle details',{exact:true}).click();await held[1].release('idle');
    await page.waitForTimeout(650);expect(reads).toBe(2);await expect(page.locator('output')).toHaveText('none');
    await page.getByText('Next pipeline',{exact:true}).click();await page.getByText('Toggle details',{exact:true}).click();await expect.poll(()=>reads).toBe(3);
    await page.getByText('Change server',{exact:true}).click();await expect.poll(()=>reads).toBe(4);
    await held[3].release('idle');await expect(page.locator('output')).toHaveText('idle');await held[2].release('running');
    await page.waitForTimeout(650);await expect(page.locator('output')).toHaveText('idle');expect(reads).toBe(4);
    await page.getByText('Next pipeline',{exact:true}).click();await expect.poll(()=>reads).toBe(5);
    await page.getByText('Unmount',{exact:true}).click();await held[4].release('running');
    await page.waitForTimeout(650);expect(reads).toBe(5);await expect(page.locator('output')).toHaveCount(0);
});
