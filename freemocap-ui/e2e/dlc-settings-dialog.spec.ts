import {test, expect} from '@playwright/test';
import {build} from 'esbuild';
import {resolve} from 'node:path';

test.use({channel: process.env.PLAYWRIGHT_CHANNEL || undefined});

test('DLC setup is readable, loads models, reports errors and saves optional geometry', async ({page}, info) => {
    test.setTimeout(90000);
    page.on('pageerror', error => {throw error;});
    const calls: string[] = [];
    const imports: any[] = [];
    let holdApply = false;
    let heldApply: import('@playwright/test').Route | undefined;
    const jobs = new Map<string, {body:any,polls:number,cached:boolean}>();
    const model = {model_name:'Object tracker',sidecar_path:'C:/cache/converted.yaml',model_sha256:'abc',input_size:[480,640],resize_method:'fit',keypoint_names:Array.from({length:50},(_,i)=>`feature_${i}`),connections:[],precision:'fp32'};
    await page.route('**/*', async route => {
        const url = route.request().url();
        if (url.endsWith('/dlc/import')) {
            const body=route.request().postDataJSON(), id=String(imports.length+1);
            const cached=imports.some(previous=>JSON.stringify(previous)===JSON.stringify(body));
            imports.push(body); jobs.set(id,{body,polls:0,cached});
            return route.fulfill({json:{job_id:id,status:'queued',stage:'checking',detail:'Checking project and existing conversions',elapsed_seconds:0,estimated_remaining_seconds:null,result:null}});
        }
        if (url.includes('/dlc/import/')) {
            const id=url.split('/').at(-1)!, job=jobs.get(id)!; job.polls++;
            const resolved_checkpoint_path = job.body.checkpoint_path ?? 'C:/project/train/snapshot-029.pt';
            if(job.body.checkpoint_path?.endsWith('ambiguous.pt')&&!job.body.image_width) return route.fulfill({json:{job_id:id,status:'failed',stage:'needs_input',detail:'Project videos have different crop sizes. Specify the model input dimensions.',required_fields:['image_width','image_height'],elapsed_seconds:0.1,result:null}});
            if(job.cached||job.polls>=4) return route.fulfill({json:{job_id:id,status:'complete',stage:'ready',detail:'Model ready',elapsed_seconds:job.cached?0.3:18.8,estimated_remaining_seconds:0,cache_hit:job.cached,resolved_checkpoint_path,result:job.body.project_config_path==='C:/replacement/config.yaml'?{...model,sidecar_path:'C:/cache/replacement.yaml'}:model}});
            return route.fulfill({json:{job_id:id,status:'running',stage:'converting',detail:'Converting on CPU at 640 × 480',elapsed_seconds:job.polls*2,estimated_remaining_seconds:job.polls===1?null:job.polls===2?12:0,cache_hit:false,resolved_checkpoint_path,result:null}});
        }
        if (url.endsWith('/realtime/apply')) {
            if (holdApply) {heldApply = route; return;}
            const config = route.request().postDataJSON().realtimeConfig;
            if (config.camera_node_config.dlc_geometry_path?.endsWith('wrong-features.json')) return route.fulfill({status:422,json:{detail:'Geometry names do not match the model'}});
            return route.fulfill({json:{camera_group_id:'fixture',pipeline_id:'fixture',resolved_config:config}});
        }
        if (url.endsWith('/readiness')) return route.fulfill({json: {available: false, supported_model: 'ResNet50 GroupNorm', detail: 'Converter not installed', missing_packages: []}});
        if (url.endsWith('/inspect')) {
            const body = route.request().postDataJSON(); calls.push(body.sidecar_path);
            if (body.sidecar_path === 'bad.yaml') return route.fulfill({status: 422, json: {detail: 'Model file does not exist'}});
            return route.fulfill({json: {model_name: 'Object tracker', sidecar_path: body.sidecar_path, model_sha256: 'abc', input_size: [480,640],
                resize_method: 'fit', keypoint_names: Array.from({length:50}, (_,i) => `feature_${i}`), connections: [], precision: 'fp32'}});
        }
        return route.fulfill({contentType: 'text/html', body: '<div id="root"></div>'});
    });
    await page.addInitScript(() => {
        (window as any).pickerResponses = [];
        (window as any).pickerCalls = [];
        (window as any).electronAPI = {baseDataFolder: 'C:/fixture', invoke: async (path: string, input: unknown) => {
            if (path !== 'fileSystem.selectFile') throw new Error(`Unexpected IPC ${path}`);
            (window as any).pickerCalls.push(input);
            return {json: (window as any).pickerResponses.shift() ?? null};
        }};
    });
    await page.setViewportSize({width: 1440, height: 1000});
    await page.goto('https://dlc-settings.test/');
    const bundle = await build({stdin: {contents: `
        import React from 'react'; import {createRoot} from 'react-dom/client'; import {Provider} from 'react-redux';
        import './src/index.css'; import {store} from './src/store/store';
        import SkeletonSetup from './src/components/pipeline-progress/realtime/realtimepipeline-mediapipedetector-settings';
        import {DlcModelSettings} from './src/components/mocap-setup/dlc-model-settings';
        window.readConfig=()=>store.getState().realtime.pipelineConfig;
        window.markConnected=()=>{const config=store.getState().realtime.pipelineConfig;store.dispatch({type:'realtime/apply/fulfilled',payload:{camera_group_id:'fixture',pipeline_id:'fixture',resolved_config:config},meta:{arg:config}})};
        const root=createRoot(document.getElementById('root'));
        window.showPosthoc=()=>root.render(<Provider store={store}><DlcModelSettings context="posthoc"/></Provider>);
        function App(){const [open,setOpen]=React.useState(true);return <Provider store={store}>{open && <SkeletonSetup open onClose={()=>setOpen(false)}/>}</Provider>}
        root.render(<App/>);
    `, resolveDir: resolve('.'), loader:'tsx'}, bundle:true, write:false, outdir:'dlc-test-bundle', format:'esm',
        loader:{'.yaml':'text','.svg':'dataurl','.png':'dataurl','.webp':'dataurl','.woff2':'dataurl','.woff':'dataurl','.ttf':'dataurl'},
        external:['/images/*','/fonts/*','../images/splashmodal_art.webp','../assets/icons/import-icon.svg'], alias:{'@':resolve('src')}});
    for (const file of bundle.outputFiles) {
        if(file.path.endsWith('.css')) await page.addStyleTag({content:file.text});
        else await page.addScriptTag({content:file.text,type:'module'});
    }
    await page.getByRole('button',{name:'DLC',exact:true}).click();
    const dialog=page.getByRole('dialog',{name:'Skeleton Setup',exact:true});
    expect((await dialog.boundingBox())!.width).toBeGreaterThan(1300);
    const chooseModel = page.getByRole('button',{name:'Choose converted model…',exact:true});
    await expect(chooseModel).not.toBeVisible();
    await page.getByText('Load a different converted model (optional)',{exact:true}).click();
    await expect(chooseModel).toBeVisible();
    await expect(page.getByLabel('Model file (.yaml)',{exact:true})).not.toBeVisible();
    await expect(page.getByText('Converter not installed',{exact:false})).not.toBeVisible();
    const pick = async (response: string | null, button: string) => {
        await page.evaluate(value => (window as any).pickerResponses.push(value), response);
        await page.getByRole('button',{name:button,exact:true}).click();
    };
    await pick(null, 'Choose converted model…'); await expect(page.getByRole('alert')).toHaveCount(0);
    await pick('bad.yaml', 'Choose converted model…'); await expect(page.getByRole('alert')).toContainText('Model file does not exist');
    await pick('C:/models/object.yaml', 'Choose converted model…');
    await expect(page.getByText('Model ready and selected',{exact:true})).toBeVisible();
    expect(calls).toContain('C:/models/object.yaml');
    expect(await page.evaluate(()=>(window as any).readConfig().camera_node_config.dlc_model_path)).toBe('C:/models/object.yaml');
    await expect(page.getByRole('button',{name:'Choose DLC project…',exact:true})).toBeVisible();
    await expect(page.getByLabel('Model input width',{exact:true})).toHaveCount(0);
    await expect(page.getByRole('button',{name:'Choose training configuration…',exact:true})).toHaveCount(0);
    await page.getByText('Load a different converted model (optional)',{exact:true}).click();
    await pick('C:/project/config.yaml','Choose DLC project…');
    await expect(page.getByText('Preparing model automatically',{exact:true})).toBeVisible();
    expect(imports[0]).toEqual({project_config_path:'C:/project/config.yaml'});
    await expect(page.getByRole('button',{name:'Choose DLC project…',exact:true})).toBeDisabled();
    await expect(page.getByText('Model ready and selected',{exact:true})).toHaveCount(0);
    await expect(page.getByText('Time estimate unavailable until a conversion has been measured.',{exact:false})).toBeVisible();
    await expect(page.getByText('About 12 s remaining',{exact:false})).toBeVisible();
    await page.screenshot({path:info.outputPath('dlc-converting-desktop.png'),fullPage:true});
    await expect(page.getByText('Taking longer than the estimate.',{exact:false})).toBeVisible();
    await expect(page.getByText('Model ready and selected',{exact:true})).toBeVisible();
    await expect(page.getByText('Conversion complete.',{exact:true})).toBeVisible();
    await expect(page.getByText('Checkpoint: snapshot-029.pt',{exact:true})).toBeVisible();
    await expect(page.getByText('Next: click Done, connect your cameras, then click the lightning bolt to start tracking.',{exact:true})).toBeVisible();
    expect(await page.evaluate(()=>(window as any).readConfig().camera_node_config.dlc_model_path)).toBe('C:/cache/converted.yaml');
    await expect(chooseModel).not.toBeVisible();
    await expect(page.getByRole('button',{name:'Choose checkpoint…',exact:true})).not.toBeVisible();
    await page.getByText('Choose a different checkpoint (optional)',{exact:true}).click();
    await pick('C:/project/snapshot-best-020.pt','Choose checkpoint…');
    await expect(page.getByText('Model ready and selected',{exact:true})).toBeVisible();
    expect(imports.at(-1)).toEqual({project_config_path:'C:/project/config.yaml',checkpoint_path:'C:/project/snapshot-best-020.pt'});
    await pick('C:/project/snapshot-best-020.pt','Choose checkpoint…');
    await expect(page.getByText('Reused a saved conversion.',{exact:true})).toBeVisible();
    await pick('C:/project/ambiguous.pt','Choose checkpoint…');
    await expect(page.getByRole('alert')).toContainText('different crop sizes');
    await page.getByLabel('Model input width',{exact:true}).fill('640');
    await page.getByLabel('Model input height',{exact:true}).fill('480');
    await page.getByRole('button',{name:'Retry preparation',exact:true}).click();
    await expect(page.getByText('Model ready and selected',{exact:true})).toBeVisible();
    expect(imports.at(-1).image_width).toBe(640);
    await page.getByRole('button',{name:'Use latest checkpoint',exact:true}).click();
    await expect(page.getByText('Reused a saved conversion.',{exact:true})).toBeVisible();
    expect(imports.at(-1)).toEqual(imports[0]);
    await page.getByText('Choose a different checkpoint (optional)',{exact:true}).click();
    await page.screenshot({path:info.outputPath('dlc-loaded-desktop.png'),fullPage:true});
    await page.setViewportSize({width:860,height:720});
    await pick('C:/models/features.json', 'Choose geometry…');
    await expect(page.getByRole('status')).toContainText('Geometry saved');
    await expect(page.getByRole('status')).toBeInViewport();
    expect(await page.evaluate(()=>(window as any).readConfig().camera_node_config.dlc_geometry_path)).toBe('C:/models/features.json');
    await page.screenshot({path:info.outputPath('dlc-geometry-compact.png'),fullPage:true});
    await page.evaluate(()=>(window as any).markConnected());
    holdApply = true;
    await pick('C:/replacement/config.yaml','Choose DLC project…');
    await expect(page.getByText('Model prepared — applying selection…',{exact:true})).toBeVisible();
    await expect(page.getByText('Model ready and selected',{exact:true})).toHaveCount(0);
    await expect.poll(()=>!!heldApply).toBe(true);
    await heldApply!.fulfill({status:422,json:{detail:'Selected model could not be applied'}});
    await expect(page.getByText('Model prepared, but selection failed',{exact:true})).toBeVisible();
    await expect(page.getByRole('alert')).toContainText('Selected model could not be applied');
    await expect(page.getByText('Model ready and selected',{exact:true})).toHaveCount(0);
    expect(await page.evaluate(()=>(window as any).readConfig().camera_node_config.dlc_model_path)).toBe('C:/cache/converted.yaml');
    await page.screenshot({path:info.outputPath('dlc-selection-failed.png'),fullPage:true});
    const importsBeforeRetry = imports.length;
    holdApply = false;
    await page.getByRole('button',{name:'Retry selection',exact:true}).click();
    await expect(page.getByText('Model ready and selected',{exact:true})).toBeVisible();
    await expect(page.getByText('Selected in the running pipeline. Click Done to view tracking.',{exact:true})).toBeVisible();
    expect(imports).toHaveLength(importsBeforeRetry);
    expect(await page.evaluate(()=>(window as any).readConfig().camera_node_config.dlc_model_path)).toBe('C:/cache/replacement.yaml');
    await pick('C:/models/wrong-features.json', 'Choose geometry…');
    await expect(page.getByRole('alert')).toContainText('Geometry names do not match');
    expect(await page.evaluate(()=>(window as any).readConfig().camera_node_config.dlc_geometry_path)).toBe('C:/models/features.json');
    const pickerCalls = await page.evaluate(()=>(window as any).pickerCalls);
    expect(pickerCalls[0].filters[0].extensions).toEqual(['yaml','yml']);
    expect(pickerCalls.some((call:any)=>call.filters[0].extensions.join(',')==='json')).toBe(true);
    expect(pickerCalls.some((call:any)=>call.filters[0].extensions.join(',')==='pt,pth')).toBe(true);
    await page.getByRole('button',{name:'Done',exact:true}).click(); await expect(dialog).toHaveCount(0);
    await page.evaluate(()=>(window as any).showPosthoc());
    await page.getByRole('button',{name:'Configure DLC',exact:true}).click();
    await expect(page.getByRole('dialog',{name:'DLC tracker',exact:true})).toBeVisible();
    await page.keyboard.press('Escape'); await expect(page.getByRole('dialog')).toHaveCount(0);
});
