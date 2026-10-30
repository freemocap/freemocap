import {test, expect} from '@playwright/test';
import {build} from 'esbuild';
import path from 'node:path';

test.use({channel: process.env.PLAYWRIGHT_CHANNEL || undefined});

test.beforeEach(async ({page}) => {
    await page.route('http://localhost:53117/', route => route.fulfill({
        contentType: 'text/html', body: '<div id="root"></div>',
    }));
    await page.goto('http://localhost:53117/');
    const bundle = await build({stdin: {contents: `
        import React from 'react';
        import {createRoot} from 'react-dom/client';
        import {Provider} from 'react-redux';
        import {store} from './src/store';
        import {CameraHeaderActions} from './src/components/control-panels/camera-config-panel/camera-config-tree-view/CameraHeaderActions';
        import {createDefaultCameraConfig} from './src/store/slices/cameras/cameras-types';
        import {serverStateReceived} from './src/store/slices/connection/connection-slice';
        const config = createDefaultCameraConfig('camera', 0, 'Test camera');
        store.dispatch({type: 'cameras/detect/fulfilled', payload: [{
            id: 'camera', name: 'Test camera', index: 0, actualConfig: config,
            desiredConfig: config, hasConfigMismatch: false, selected: true,
            realtimeEnabled: true, connectionStatus: 'available',
        }]});
        window.setCameraConnection = (connected, pipelineAlive) => store.dispatch(serverStateReceived({
            kind: 'app_state', server_pid: 1, state: {
                camera_groups: connected ? {current: {id: 'current', backend: 'python', alive: true,
                    paused: false, configs: {camera: config}, cameras: {}, recording_in_progress: false}} : {},
                realtime_pipelines: pipelineAlive === undefined ? [] : [{id: 'pipeline',
                    camera_group_id: 'previous', camera_ids: ['camera'], alive: pipelineAlive}],
            },
        }));
        window.testStore = store;
        createRoot(document.getElementById('root')).render(<Provider store={store}><CameraHeaderActions/></Provider>);
    `, resolveDir: path.resolve('.'), loader: 'tsx'}, bundle: true, write: false,
        outdir: 'camera-controls-test-bundle', format: 'esm', jsx: 'automatic',
        loader: {'.yaml': 'text'}, alias: {'@': path.resolve('src')},
    });
    for (const file of bundle.outputFiles) {
        if (file.path.endsWith('.css')) await page.addStyleTag({content: file.text});
        else if (file.path.endsWith('.js')) await page.addScriptTag({type: 'module', content: file.text});
    }
    await expect.poll(() => page.evaluate(() => Boolean((window as any).testStore))).toBe(true);
});

test('Recommend stays present through camera disconnect and reconnect', async ({page}) => {
    const recommend = page.locator('button').filter({has: page.locator('.recommendexposure-icon')});
    await expect(recommend).toHaveCount(1);
    await expect(recommend).toBeDisabled();
    await page.evaluate(() => (window as any).setCameraConnection(true));
    await expect(recommend).toBeEnabled();
    await page.evaluate(() => (window as any).setCameraConnection(false));
    await expect(recommend).toHaveCount(1);
    await expect(recommend).toBeDisabled();
    await page.evaluate(() => (window as any).setCameraConnection(true));
    await expect(recommend).toBeEnabled();
});

test('Recommend cannot start a second request while settings are applying', async ({page}) => {
    await page.evaluate(() => {
        (window as any).setCameraConnection(true);
        (window as any).testStore.dispatch({type: 'cameras/connect/pending'});
    });
    await expect(page.locator('button').filter({has: page.locator('.recommendexposure-icon')})).toBeDisabled();
});

test('Stopped reconstruction is not reported as connected', async ({page}) => {
    await page.evaluate(() => (window as any).setCameraConnection(true, true));
    await expect.poll(() => page.evaluate(() => (window as any).testStore.getState().realtime.isConnected)).toBe(true);
    await page.evaluate(() => (window as any).setCameraConnection(true, false));
    await expect.poll(() => page.evaluate(() => (window as any).testStore.getState().realtime.isConnected)).toBe(false);
    expect(await page.evaluate(() => (window as any).testStore.getState().realtime.pipelineId)).toBeNull();
});
