import {test, expect} from '@playwright/test';
import {build} from 'esbuild';
import path from 'node:path';
import fs from 'node:fs';
import AxeBuilder from '@axe-core/playwright';

test.use({channel: process.env.PLAYWRIGHT_CHANNEL});

test('Mocap modal visual sections and complete processing request', async ({page},info) => {
    page.on('pageerror', error => {throw error;});
    await page.setViewportSize({width:1280,height:720});
    const requests: unknown[] = [];
    await page.route('**/*', async route => {
        const url = route.request().url();
        if (route.request().method() === 'POST') {requests.push(route.request().postDataJSON()); await route.fulfill({json:{success:true,task_id:'baseline-task'}}); return;}
        if (url.includes('/stages?')) {await route.fulfill({json:{selected_run_id:0,runs:[]}}); return;}
        if (url.includes('execution_providers')) {await route.fulfill({json:{available:['CPUExecutionProvider']}}); return;}
        await route.fulfill({json:{server_instance_id:'11111111-1111-4111-8111-111111111111',revision:0,recording_owners:[],tasks:[]}});
    });
    await page.route('http://localhost:53117/', route => route.fulfill({contentType:'text/html',body:'<main id="root"></main>'}));
    await page.goto('http://localhost:53117/');
    const bundle = await build({
        stdin: {resolveDir: path.resolve('.'), loader: 'tsx', contents: `
            import './src/styles/App.css';
            import React from 'react';
            import {createRoot} from 'react-dom/client';
            import {Provider} from 'react-redux';
            import {MemoryRouter} from 'react-router-dom';
            import {activeRecordingSet} from './src/store/slices/active-recording/active-recording-slice';
            import {serverUrls} from './src/constants/server-urls';
            import {store} from './src/store/store';
            import {calibrationLoadedFromBundle} from './src/store/slices/calibration';
            import Section from './src/components/common/settings-layout/settings-section';
            import Summary from './src/components/mocap-setup/camera-geometry-summary';
            import Modal from './src/components/mocap-setup/mocap-setup-modal';
            serverUrls.setHost('localhost'); serverUrls.setPort(53117);
            store.dispatch(activeRecordingSet({baseDirectory:'/recordings',recordingName:'baseline',origin:'browsed'}));
            store.dispatch(calibrationLoadedFromBundle({path:'/recordings/baseline/calibration.toml', cameras:[{},{},{}],metadata:{aligned:false}}));
            createRoot(document.getElementById('root')!).render(<Provider store={store}><MemoryRouter>
                <Modal mode="playback"/>
            </MemoryRouter></Provider>);
        `},
        external: ['/images/*', '../images/*', '../assets/icons/import-icon.svg'],
        bundle: true, write: false, outdir: 'geometry-test', format: 'esm',
        alias: {'@': path.resolve('src')}, loader: {'.yaml': 'text', '.webp': 'dataurl', '.svg': 'dataurl', '.png': 'dataurl', '.woff': 'dataurl', '.woff2': 'dataurl', '.ttf': 'dataurl'},
        plugins: [{name: 'external-boundaries', setup(builder) {
            builder.onResolve({filter: /useRecordingCalibrationDefault$/}, () => ({path:'discovery',namespace:'mock'}));
            builder.onResolve({filter: /^@\/services$/}, () => ({path: 'services', namespace: 'mock'}));
            builder.onResolve({filter: /useCalibration$/}, () => ({path: 'calibration', namespace: 'mock'}));
            builder.onResolve({filter: /ImportVideosModal$/}, () => ({path: 'import', namespace: 'mock'}));
            builder.onLoad({filter: /.*/, namespace: 'mock'}, args => ({loader: 'ts', resolveDir: path.resolve('.'), contents:
                args.path === 'discovery' ? 'export const useRecordingCalibrationDefault=()=>{};' :
                args.path === 'services' ? `export const useElectronIPC=()=>({api:null,isElectron:false}); export const useServer=()=>({connectedCameraIds:[],isConnected:true,isFailed:false}); export const serverUrls={getHttpUrl:()=> 'http://localhost:53117',endpoints:{onnxExecutionProviders:'http://localhost:53117/freemocap/onnx/execution_providers'}};` :
                args.path === 'import' ? 'export default function ImportModal(){return null;}' :
                `import {useAppSelector} from '@/store'; export const useCalibration=()=>({config:useAppSelector(state=>state.calibration.config),isLoading:false,isRecording:false,updateCalibrationConfig:()=>{}});`
            }));
        }}],
    });

    for (const file of bundle.outputFiles) {
        if (file.path.endsWith('.css')) await page.addStyleTag({content:file.text});
        else await page.addScriptTag({content:file.text,type:'module'});
    }
    await page.addStyleTag({content:'*,*::before,*::after{scroll-behavior:auto!important;animation:none!important;transition:none!important}'});
    const modal=page.getByRole('dialog',{name:'Mocap processing',exact:true});
    await expect(modal).toBeVisible();
    const contrast: unknown[] = [];
    for (const section of ['Recording directory','Processing stages','Detectors','Camera geometry','Triangulation','Post-processing','Exports','Blender']) {
        await page.getByRole('navigation',{name:'Mocap setup sections'}).getByRole('button',{name:section,exact:true}).click();
        const result=await new AxeBuilder({page}).include('[aria-label="Mocap processing"]').withRules(['color-contrast']).analyze();
        contrast.push({section,violations:result.violations,incomplete:result.incomplete});
        await expect.soft(modal).toHaveScreenshot(`mocap-${section.toLowerCase().replaceAll(' ','-')}.png`,{animations:'disabled'});
    }
    await page.getByRole('button',{name:'Process Mocap',exact:true}).click();
    await expect.poll(()=>requests.length).toBe(1);
    expect(requests[0]).toEqual(JSON.parse(fs.readFileSync(path.resolve('e2e/fixtures/mocap-processing-request.baseline.json'),'utf8')));
    await info.attach('modal-contrast',{body:JSON.stringify(contrast,null,2),contentType:'application/json'});
    expect.soft(contrast.flatMap((r:any)=>r.violations),'Text contrast violations; see attachment').toEqual([]);
});
