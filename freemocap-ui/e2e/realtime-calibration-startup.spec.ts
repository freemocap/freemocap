import {test, expect} from '@playwright/test';
import {build} from 'esbuild';
import path from 'node:path';
import {calibrationFixture} from './fixtures/calibration';

test.use({channel: process.env.PLAYWRIGHT_CHANNEL});

for (const scenario of ['available', 'missing', 'unreadable']) {
test(`starting live capture resolves ${scenario} calibration without the calibration panel`, async ({page}) => {
    page.on('pageerror', error => {throw error;});
    const requests: any[] = [];
    await page.route('**/realtime/config', route => route.fulfill({json: null}));
    await page.route('**/calibration/most-recent', route => route.fulfill(scenario === 'unreadable'
        ? {status: 422, json: {detail: 'Calibration file is unreadable'}}
        : {json: scenario === 'missing' ? null : calibrationFixture('C:/latest.toml')}));
    await page.route('**/realtime/apply', route => {
        requests.push(route.request().postDataJSON());
        return route.fulfill({json: {camera_group_id: 'cameras', pipeline_id: 'live'}});
    });
    await page.route('http://localhost:53117/', route => route.fulfill({contentType: 'text/html', body: '<div id="root"></div>'}));
    await page.goto('http://localhost:53117/');
    const bundle = await build({stdin: {contents: `
        import React from 'react';
        import {createRoot} from 'react-dom/client';
        import {Provider} from 'react-redux';
        import {store, useAppSelector} from './src/store';
        import {useRealtimePipelineSync} from './src/hooks/useRealtimePipelineSync';
        function Controls() {
            const {toggleConnection, isLoading, error} = useRealtimePipelineSync();
            const selected = useAppSelector(state => state.calibration.loadedCalibration?.path ?? 'none');
            return <><button disabled={isLoading} onClick={toggleConnection}>Start live capture</button>
                <output aria-label="Calibration">{selected}</output><output aria-label="Error">{error}</output></>;
        }
        createRoot(document.getElementById('root')!).render(<Provider store={store}><Controls/></Provider>);
    `, resolveDir: path.resolve('.'), loader: 'tsx'}, bundle: true, write: false,
        outdir: 'startup-test-bundle', format: 'esm', jsx: 'automatic',
        loader: {'.yaml': 'text'}, alias: {'@': path.resolve('src')}});
    for (const file of bundle.outputFiles) {
        if (file.path.endsWith('.css')) await page.addStyleTag({content: file.text});
        else await page.addScriptTag({content: file.text, type: 'module'});
    }
    await page.getByRole('button', {name: 'Start live capture'}).click();
    if (scenario === 'unreadable') {
        await expect(page.getByLabel('Error', {exact: true})).toContainText('Calibration file is unreadable');
        expect(requests).toEqual([]);
        return;
    }
    await expect.poll(() => requests.map(request => request.realtimeConfig.aggregator_config.calibration_toml_path)).toEqual([
        scenario === 'missing' ? null : 'C:/latest.toml',
    ]);
    await expect(page.getByLabel('Calibration', {exact: true})).toHaveText(scenario === 'missing' ? 'none' : 'C:/latest.toml');
    if (scenario === 'available') expect(requests[0].realtimeConfig.camera_node_config.charuco_board.squares_x).toBe(5);
    expect(requests[0].realtimeConfig.aggregator_config.skeleton_fitting_enabled).toBe(true);
});
}
