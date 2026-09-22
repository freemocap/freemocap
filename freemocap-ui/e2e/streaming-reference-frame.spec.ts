import {test, expect} from '@playwright/test';
import {build} from 'esbuild';
import path from 'node:path';

test.use({channel: process.env.PLAYWRIGHT_CHANNEL});

test('streaming calibration editor applies and resets the live reference offset', async ({page}) => {
    let releaseApply: () => void = () => {throw new Error('Apply response is not pending');};
    const applyResponse = new Promise<void>(resolve => {releaseApply = resolve;});
    page.on('pageerror', error => {throw error;});
    const requests: {realtimeConfig: {aggregator_config: {
        calibration_toml_path: string; reference_transform: {matrix: number[]} | null;
    }}}[] = [];
    await page.route('http://localhost:53117/**', async route => {
        if (route.request().method() !== 'POST') {
            await route.fulfill({status: 404});
            return;
        }
        requests.push(route.request().postDataJSON());
        await applyResponse;
        await route.fulfill({json: {camera_group_id: 'cameras', pipeline_id: 'live'}});
    });
    await page.route('http://localhost:53117/', route => route.fulfill({contentType: 'text/html', body: '<div id="root"></div>'}));
    await page.goto('http://localhost:53117/');
    const bundle = await build({
        stdin: {contents: `
            import React from 'react';
            import {createRoot} from 'react-dom/client';
            import {Provider} from 'react-redux';
            import {store} from './src/store/store';
            import {calibrationFixture} from './e2e/fixtures/calibration';
            import {calibrationLoadedFromBundle} from './src/store/slices/calibration';
            import Controls from './src/components/pipeline-progress/calibration-progress/calibration-reference-frame';
            import './src/styles/calibration.css';
            import './src/styles/App.css';
            import './src/styles/color.css';
            import './src/styles/button-sm.css';
            import {Canvas, useFrame} from '@react-three/fiber';
            import {WorkerDataProvider} from './src/components/viewport3d/WorkerDataContext';
            import {ViewportStateProvider} from './src/components/viewport3d/scene/ViewportStateContext';
            import {MocapCameraRenderer} from './src/components/viewport3d/renderers/MocapCameraRenderer';
            import {ReferenceFrame} from './src/components/viewport3d/scene/ReferenceFrame';
            import {workerDataStore} from './src/components/viewport3d/WorkerDataStore';
            import {useReferenceFrameForwarder} from './src/components/viewport3d/hooks/useReferenceFrameForwarder';
            const channel = new MessageChannel();
            channel.port2.onmessage = event => workerDataStore.dispatch(event.data.type, event.data.data);
            const calibration = calibrationFixture('C:/calibration.toml');
            calibration.cameras[0].world_position = [100, 0, 0];
            function ObserveScene() {
                useFrame(({scene, gl, camera}) => {
                    gl.render(scene, camera);
                    const mesh = scene.getObjectsByProperty('type', 'Mesh')[0];
                    if (mesh) document.getElementById('camera-position')!.textContent = mesh.matrixWorld.elements.slice(12, 15).map(Math.round).join(',');
                    const axes = scene.getObjectByName('Transformed reference frame');
                    document.getElementById('axes-position')!.textContent = axes ? axes.matrixWorld.elements.slice(12, 15).map(Math.round).join(',') : 'none';
                    document.getElementById('axes-direction')!.textContent = axes ? axes.matrixWorld.elements.slice(0, 3).map(Math.round).join(',') : 'none';
                }, 1);
                return null;
            }
            function Harness() {
                useReferenceFrameForwarder(channel.port1, true, calibration);
                const [calibrationPath, setCalibrationPath] = React.useState<string | null>(null);
                return <>
                    <button onClick={() => {
                        setCalibrationPath('C:/calibration.toml');
                        store.dispatch(calibrationLoadedFromBundle(calibration));
                        store.dispatch({type: 'realtime/apply/fulfilled', payload: {camera_group_id: 'cameras', pipeline_id: 'live'},
                            meta: {arg: store.getState().realtime.pipelineConfig}});
                    }}>Load test calibration</button>
                    <Controls calibrationPath={calibrationPath}/>
                    <output id="camera-position" aria-label="Rendered camera position"/>
                    <output id="axes-position" aria-label="Rendered transformed axes"/>
                    <output id="axes-direction" aria-label="Transformed X direction"/>
                    <div style={{position: 'absolute', right: 0, top: 0, width: 300, height: 200, pointerEvents: 'none'}}><Canvas frameloop="demand">
                        <WorkerDataProvider><ViewportStateProvider>
                            <MocapCameraRenderer/><ReferenceFrame/><ObserveScene/>
                        </ViewportStateProvider></WorkerDataProvider>
                    </Canvas></div></>;
            }
            createRoot(document.getElementById('root')!).render(<Provider store={store}><Harness/></Provider>);
        `, resolveDir: path.resolve('.'), loader: 'tsx'},
        bundle: true, write: false, outdir: 'streaming-reference-test-bundle', format: 'esm', jsx: 'automatic',
        loader: {'.yaml': 'text'}, alias: {'@': path.resolve('src')},
        plugins: [{name: 'omit-webgl-preview', setup(builder) {
            builder.onResolve({filter: /./}, args =>
                args.kind === 'url-token' ? {path: args.path, external: true} : undefined);
            builder.onLoad({filter: /transform-preview\.tsx$/}, () => ({
                contents: 'export default function Preview() { return null; }', loader: 'tsx',
            }));
        }}],
    });
    for (const file of bundle.outputFiles) {
        if (file.path.endsWith('.css')) await page.addStyleTag({content: file.text});
        else await page.addScriptTag({content: file.text, type: 'module'});
    }
    await expect(page.getByRole('button', {name: 'Reference frame…', exact: true})).toBeVisible();
    await expect(page.getByLabel('Rendered camera position')).toHaveText('0,100,0');
    await expect(page.getByRole('button', {name: 'Reference frame…', exact: true})).toBeEnabled();
    await expect(page.getByRole('button', {name: 'Reference frame…', exact: true})).toHaveCSS('border-top-style', 'solid');
    await expect(page.getByText('Load or record a calibration to set the reference frame.', {exact: true})).toHaveCount(0);
    await page.getByRole('button', {name: 'Reference frame…', exact: true}).click();
    await page.getByRole('textbox', {name: 'Position: X mm', exact: true}).click();
    await page.getByRole('textbox', {name: 'Position: X mm', exact: true}).fill('50');
    await page.getByRole('button', {name: 'Accept transformation', exact: true}).click();
    await expect(page.getByLabel('Rendered camera position')).toHaveText('50,100,0');
    await expect(page.getByLabel('Rendered transformed axes')).toHaveText('50,0,0');
    await expect(page.getByLabel('Runtime transformation')).toContainText('[50, 0, 0]');
    await expect(page.getByRole('dialog', {name: 'Custom reference frame'})).toHaveCount(0);
    expect(requests).toHaveLength(0);
    await page.getByRole('button', {name: 'Load test calibration', exact: true}).click();
    await page.getByRole('button', {name: 'Reference frame…', exact: true}).click();
    const position = page.getByRole('textbox', {name: 'Position: X mm', exact: true});
    await position.click();
    await position.fill('125');
    await page.getByRole('textbox', {name: 'Euler · XYZ: Z °', exact: true}).click();
    await page.getByRole('textbox', {name: 'Euler · XYZ: Z °', exact: true}).fill('90');
    await page.getByRole('button', {name: 'Accept transformation', exact: true}).click();
    await expect(page.getByText('Custom reference offset', {exact: true})).toBeVisible();
    expect(requests).toHaveLength(1);
    expect(requests[0].realtimeConfig.aggregator_config.calibration_toml_path).toBe('C:/calibration.toml');
    const matrix = requests[0].realtimeConfig.aggregator_config.reference_transform?.matrix;
    expect(matrix).toHaveLength(16);
    [0,-1,0,125,1,0,0,0,0,0,1,0,0,0,0,1].forEach((value, index) =>
        expect(matrix![index]).toBeCloseTo(value, 10));
    await expect(page.getByLabel('Rendered camera position')).toHaveText('25,0,0');
    await expect(page.getByLabel('Rendered transformed axes')).toHaveText('125,0,0');
    await expect(page.getByLabel('Transformed X direction')).toHaveText('0,1,0');
    await expect(page.getByLabel('Runtime transformation')).toContainText('[0.707, 0, 0, 0.707]');
    await expect(page.getByLabel('Runtime transformation')).toContainText('[125, 0, 0]');
    releaseApply();
    await page.getByRole('button', {name: 'Reference frame…', exact: true}).click();
    await expect(position).toHaveValue('125');
    await page.getByRole('button', {name: 'Cancel', exact: true}).click();
    expect(requests).toHaveLength(1);
    await page.getByRole('button', {name: 'Reset frame', exact: true}).click();
    await expect(page.getByLabel('Rendered camera position')).toHaveText('0,100,0');
    await expect(page.getByLabel('Rendered transformed axes')).toHaveText('none');
    await expect(page.getByLabel('Runtime transformation')).toHaveCount(0);
    expect(requests).toHaveLength(2);
    expect(requests[1].realtimeConfig.aggregator_config.reference_transform).toBeNull();
});
