import {test, expect} from '@playwright/test';
import {build} from 'esbuild';
import path from 'node:path';

test.use({channel: process.env.PLAYWRIGHT_CHANNEL});

test('graph controls use settings styling and board dialog escapes the scrolling modal', async ({page}) => {
    await page.setViewportSize({width:1280,height:720});
    await page.route('http://localhost:53117/', route => route.fulfill({contentType:'text/html',body:'<main id="root"></main>'}));
    await page.goto('http://localhost:53117/');
    const bundle = await build({
        stdin: {resolveDir: path.resolve('.'), loader: 'tsx', contents: `
            import './src/styles/App.css';
            import React from 'react';
            import {createRoot} from 'react-dom/client';
            import {Provider} from 'react-redux';
            import {MemoryRouter} from 'react-router-dom';
            import {store} from './src/store/store';
            import {calibrationLoadedFromBundle} from './src/store/slices/calibration';
            import Section from './src/components/common/settings-layout/settings-section';
            import Summary from './src/components/mocap-setup/camera-geometry-summary';
            import Modal from './src/components/mocap-setup/mocap-setup-modal';
            store.dispatch(calibrationLoadedFromBundle({path:'C:/recordings/freemocap_test_data/freemocap_test_data_camera_calibration.toml', cameras:[{},{},{}],metadata:{aligned:false}}));
            createRoot(document.getElementById('root')!).render(<Provider store={store}><MemoryRouter>
                <Modal mode="playback"/>
            </MemoryRouter></Provider>);
        `},
        external: ['/images/*', '../images/*', '../assets/icons/import-icon.svg'],
        bundle: true, write: false, outdir: 'geometry-test', format: 'esm',
        alias: {'@': path.resolve('src')}, loader: {'.yaml': 'text', '.webp': 'dataurl', '.svg': 'dataurl', '.png': 'dataurl', '.woff': 'dataurl', '.woff2': 'dataurl', '.ttf': 'dataurl'},
        plugins: [{name: 'external-boundaries', setup(builder) {
            builder.onResolve({filter: /^@\/services$/}, () => ({path: 'services', namespace: 'mock'}));
            builder.onResolve({filter: /useCalibration$/}, () => ({path: 'calibration', namespace: 'mock'}));
            builder.onResolve({filter: /ImportVideosModal$/}, () => ({path: 'import', namespace: 'mock'}));
            builder.onLoad({filter: /.*/, namespace: 'mock'}, args => ({loader: 'ts', resolveDir: path.resolve('.'), contents:
                args.path === 'services' ? `export const useElectronIPC=()=>({api:null,isElectron:false}); export const useServer=()=>({connectedCameraIds:[],isConnected:true,isFailed:false}); export const serverUrls={};` :
                args.path === 'import' ? 'export default function ImportModal(){return null;}' :
                `import {useAppSelector} from '@/store'; export const useCalibration=()=>({config:useAppSelector(state=>state.calibration.config),isLoading:false,isRecording:false,updateCalibrationConfig:()=>{}});`
            }));
        }}],
    });

    for (const file of bundle.outputFiles) {
        if (file.path.endsWith('.css')) await page.addStyleTag({content:file.text});
        else await page.addScriptTag({content:file.text,type:'module'});
    }
    await page.getByRole('navigation',{name:'Mocap setup sections'}).getByRole('button',{name:'Processing stages',exact:true}).click();
    const pipeline=page.getByRole('combobox',{name:'Processing pipeline',exact:true});
    await expect(pipeline).toHaveValue('typed_dataflow');
    await expect(pipeline.locator('option')).toHaveText(['Typed data flow graph V1', 'Legacy post hoc pipeline']);
    await pipeline.selectOption('current');
    await expect(pipeline).toHaveValue('current');
    await expect(page.getByRole('combobox',{name:'Tracking device',exact:true})).toHaveCount(0);
    await pipeline.selectOption('typed_dataflow');
    expect(await pipeline.evaluate(el=>!!el.closest('.setting-select-input'))).toBe(true);
    await expect(page.getByRole('combobox',{name:'Tracking device',exact:true})).toBeVisible();
    await page.getByRole('button',{name:/^Configure board/}).click();
    const board=page.getByRole('dialog',{name:'ChArUco board settings',exact:true});
    await expect(board).toBeVisible();
    expect(await board.evaluate(el=>el.parentElement===document.body)).toBe(true);
    expect(await board.evaluate(el=>{const r=el.getBoundingClientRect();return r.top>=0&&r.left>=0&&r.right<=innerWidth&&r.bottom<=innerHeight;})).toBe(true);
    await page.getByRole('button',{name:'Close board settings',exact:true}).click();
    await expect(board).toHaveCount(0);
});
