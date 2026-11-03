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

test('preparation hook makes no recurring closed, idle or terminal requests and cleans up polling', async ({page}) => {
    test.setTimeout(60000);
    let status='idle', gets=0, posts=0, holdNext=false;
    let releaseHeld: (()=>Promise<void>) | null=null;
    await page.route('**/*', route => {
        if (!route.request().url().includes('/freemocap/onnx/preparation/')) return route.fulfill({contentType:'text/html',body:'<div id="root"></div>'});
        if(route.request().method()==='POST'){posts++;status='running';}else gets++;
        const response={contentType:'application/json',body:JSON.stringify({pipeline_id:'p',status,phase:status,elapsed_seconds:0,model_name:null,message:null,error:null,can_prepare:status==='idle',can_cancel:status==='running',requested_provider:'trt',active_provider:'cuda'})};
        if(holdNext){holdNext=false;releaseHeld=async()=>{await route.fulfill(response).catch(()=>{});};return;}
        return route.fulfill(response);
    });
    await page.goto('https://preparation-hook.test/');
    const bundle=await build({stdin:{contents:`
        import React from 'react'; import {createRoot} from 'react-dom/client'; import {Provider} from 'react-redux'; import {configureStore} from '@reduxjs/toolkit';
        import {useOnnxPreparation} from './src/hooks/useOnnxPreparation';
        const store=configureStore({reducer:(state={connection:{isConnected:true,serverPid:1}},action)=>action.type==='server' ? {...state,connection:{...state.connection,serverPid:state.connection.serverPid+1}}:state});
        function Details({open}){const state=useOnnxPreparation('p',open);return <><output>{state.snapshot?.status??'none'}</output><button onClick={state.onPrepare}>Prepare</button></>}
        function App(){const[open,setOpen]=React.useState(false);const[mounted,setMounted]=React.useState(true);return <Provider store={store}><button onClick={()=>setOpen(!open)}>Toggle details</button><button onClick={()=>store.dispatch({type:'server'})}>Change server</button><button onClick={()=>setMounted(false)}>Unmount</button>{mounted&&<Details open={open}/>}</Provider>}
        createRoot(document.getElementById('root')).render(<App/>);
    `,loader:'tsx',resolveDir:resolve('.')},bundle:true,write:false,format:'esm',alias:{'@':resolve('src')},loader:{'.yaml':'text'},logLevel:'silent'});
    await page.addScriptTag({content:bundle.outputFiles[0].text,type:'module'});
    await page.waitForTimeout(1100); expect(gets).toBe(0);
    await page.getByText('Toggle details',{exact:true}).click(); await expect(page.locator('output')).toHaveText('idle');
    await page.waitForTimeout(1100); expect(gets).toBe(1); expect(posts).toBe(0);
    await page.getByText('Prepare',{exact:true}).click(); await expect(page.locator('output')).toHaveText('running');
    await expect.poll(()=>gets).toBeGreaterThan(2); expect(posts).toBe(1);
    await page.getByText('Toggle details',{exact:true}).click(); const closedGets=gets;
    await page.waitForTimeout(1100); expect(gets).toBe(closedGets);
    status='activated'; await page.getByText('Toggle details',{exact:true}).click(); await expect(page.locator('output')).toHaveText('activated');
    const terminalGets=gets; await page.waitForTimeout(1100); expect(gets).toBe(terminalGets);
    await page.getByText('Change server',{exact:true}).click(); await expect.poll(()=>gets).toBe(terminalGets+1);
    await page.waitForTimeout(1100); expect(gets).toBe(terminalGets+1);
    status='running'; holdNext=true; await page.getByText('Toggle details',{exact:true}).click(); await page.getByText('Toggle details',{exact:true}).click();
    await expect.poll(()=>releaseHeld!==null).toBe(true);
    await page.getByText('Toggle details',{exact:true}).click(); await releaseHeld!(); releaseHeld=null;
    const lateClosedGets=gets; await page.waitForTimeout(1100); expect(gets).toBe(lateClosedGets); await expect(page.locator('output')).toHaveText('none');
    status='activated'; await page.getByText('Toggle details',{exact:true}).click(); await expect(page.locator('output')).toHaveText('activated');
    status='running'; holdNext=true; await page.getByText('Toggle details',{exact:true}).click(); await page.getByText('Toggle details',{exact:true}).click();
    await expect.poll(()=>releaseHeld!==null).toBe(true);
    status='activated'; await page.getByText('Change server',{exact:true}).click(); await expect(page.locator('output')).toHaveText('activated');
    await releaseHeld!(); releaseHeld=null; const changedGets=gets;
    await page.waitForTimeout(1100); expect(gets).toBe(changedGets); await expect(page.locator('output')).toHaveText('activated');
    status='running'; holdNext=true; await page.getByText('Toggle details',{exact:true}).click(); await page.getByText('Toggle details',{exact:true}).click();
    await expect.poll(()=>releaseHeld!==null).toBe(true);
    await page.getByText('Unmount',{exact:true}).click(); const unmountedGets=gets;
    await releaseHeld!();
    await page.waitForTimeout(1100); expect(gets).toBe(unmountedGets);
});
