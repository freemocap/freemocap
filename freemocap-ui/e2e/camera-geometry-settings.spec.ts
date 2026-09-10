import {test, expect} from '@playwright/test';
import {build} from 'esbuild';
import path from 'node:path';

test.use({channel: process.env.PLAYWRIGHT_CHANNEL});

test('camera geometry keeps its summary visible without repeating the calibration panel', async ({page}) => {
    const errors: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.setViewportSize({width: 1000, height: 760});
    await page.route('http://geometry.test/', route => route.fulfill({contentType: 'text/html', body: '<html></html>'}));
    await page.goto('http://geometry.test/');
    await page.setContent('<main id="root" style="max-width:760px;margin:40px auto"></main>');

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
            import Settings from './src/components/mocap-setup/capture-volume-settings';
            store.dispatch(calibrationLoadedFromBundle({path:'C:/recordings/freemocap_test_data/freemocap_test_data_camera_calibration.toml', cameras:[{},{},{}],metadata:{groundplane_applied:false}}));
            createRoot(document.getElementById('root')!).render(<Provider store={store}><MemoryRouter>
                <div className="settings-layout"><Section title="Camera geometry" summary={<Summary/>}><Settings mode="playback"/></Section></div>
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
        if (file.path.endsWith('.css')) await page.addStyleTag({content: file.text});
        else await page.addScriptTag({content: file.text, type: 'module'});
    }
    expect(errors).toEqual([]);
    const header = page.getByRole('button', {name: /^Camera geometry/});
    await expect(header).toContainText('Calibrated · 3 cameras');
    await expect(header).toContainText('freemocap_test_data_camera_calibration.toml');
    await expect(page.getByRole('button', {name: 'Set up calibration'})).toHaveCount(1);
    await expect(page.locator('.calibration-module-calibarted')).toHaveCount(0);
    await expect(page.getByRole('button', {name: 'Use recording calibration'})).toHaveCount(0);
    await expect(page.getByRole('button', {name: 'Calibrate from active recording', exact: true})).toHaveClass(/accent-outline/);
    await expect(page.getByText('Capture volume alignment', {exact: true})).toBeVisible();
    await expect(page.getByText('Applied when you process mocap.', {exact: false})).toHaveCount(0);
    await expect(page.getByRole('switch', {name: 'Apply custom transform', exact: true})).not.toBeChecked();
    await page.getByRole('button', {name: 'Reference frame…', exact: true}).click();
    await expect(page.getByRole('dialog', {name: 'Custom reference frame'})).toBeVisible();
    await page.getByRole('button', {name: 'Accept transformation', exact: true}).click();
    await expect(page.getByRole('dialog', {name: 'Custom reference frame'})).toHaveCount(0);
    await expect(page.getByRole('switch', {name: 'Apply custom transform', exact: true})).toBeChecked();
    await expect(page.getByLabel('Defined transformation')).toContainText('q (wxyz)');
    await page.screenshot({path: 'test-results/camera-geometry-expanded.png'});
    await page.getByRole('button', {name: 'Set up calibration'}).click();
    await expect(page.getByRole('button', {name: 'Use recording calibration'})).toBeVisible();
    await page.screenshot({path: 'test-results/camera-geometry-source.png', animations: 'disabled'});
    await page.getByRole('button', {name: 'Set up calibration'}).click();
    await header.click();
    await expect(header).toContainText('Align to person');
    await expect(page.getByRole('switch', {name: 'Align to person'})).toBeHidden();
    await page.screenshot({path: 'test-results/camera-geometry-collapsed.png'});
    expect(errors).toEqual([]);
});








