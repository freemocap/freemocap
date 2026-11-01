import {test, expect} from '@playwright/test';
import {build} from 'esbuild';
import {resolve} from 'node:path';

test.use({channel: process.env.PLAYWRIGHT_CHANNEL || undefined});

test('Skeleton Setup selects the hybrid through the real realtime store', async ({page}) => {
    page.on('pageerror', error => {throw error;});
    // Every request is intercepted; this test cannot contact the user's server.
    await page.route('**/*', route => route.fulfill({contentType: 'text/html',
        body: '<div id="root"></div>'}));
    await page.goto('https://skeleton-settings.test/');
    const bundle = await build({
        stdin: {contents: `
            import React from 'react';
            import {createRoot} from 'react-dom/client';
            import {Provider} from 'react-redux';
            import {store} from './src/store/store';
            import SkeletonSetup from './src/components/pipeline-progress/realtime/realtimepipeline-mediapipedetector-settings';
            window.readPipelineConfig = () => store.getState().realtime.pipelineConfig;
            createRoot(document.getElementById('root')).render(
                <Provider store={store}><SkeletonSetup open onClose={() => {}} /></Provider>);
        `, resolveDir: resolve('.'), loader: 'tsx'},
        bundle: true, write: false, outdir: 'skeleton-test-bundle', format: 'esm',
        loader: {'.yaml': 'text'}, alias: {'@': resolve('src')},
    });
    for (const file of bundle.outputFiles) {
        if (file.path.endsWith('.css')) await page.addStyleTag({content: file.text});
        else await page.addScriptTag({content: file.text, type: 'module'});
    }
    await expect(page.getByText('Skeleton Setup', {exact: true})).toBeVisible();
    await page.getByRole('button', {name: 'RTMW + MediaPipe hands', exact: true}).click();
    await expect.poll(() => page.evaluate(() =>
        (window as any).readPipelineConfig().camera_node_config.detector_type))
        .toBe('rtmw_mediapipe_hands');
    await expect(page.getByText('Execution provider', {exact: true})).toBeVisible();
    await expect(page.getByText('Detection confidence', {exact: true})).toBeVisible();
    await expect(page.getByText('Model size', {exact: true})).toHaveCount(0);
    await expect(page.getByText('The execution provider applies to RTMW', {exact: false})).toBeVisible();

    await page.getByRole('button', {name: 'MediaPipe', exact: true}).click();
    await expect(page.getByText('Model size', {exact: true})).toBeVisible();
    await expect(page.getByText('Execution provider', {exact: true})).toHaveCount(0);
    await page.getByRole('button', {name: 'Heavy', exact: true}).click();
    await expect.poll(() => page.evaluate(() =>
        (window as any).readPipelineConfig().camera_node_config.mediapipe_model_complexity)).toBe('heavy');
    await page.getByRole('button', {name: 'RTMW', exact: true}).click();
    await expect.poll(() => page.evaluate(() =>
        (window as any).readPipelineConfig().camera_node_config.detector_type)).toBe('rtmpose');
    await expect(page.getByText('Detection confidence', {exact: true})).toHaveCount(0);
});
