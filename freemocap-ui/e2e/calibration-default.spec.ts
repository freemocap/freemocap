import {test, expect} from '@playwright/test';
import {build} from 'esbuild';
import path from 'node:path';

test.use({channel: process.env.PLAYWRIGHT_CHANNEL});

for (const runningPath of [undefined, 'C:/running.toml', null]) {
test(`startup restores ${runningPath} without writing and explicit selection updates the pipeline`, async ({page}) => {
    page.on('pageerror', error => {throw error;});
    let discoveries = 0;
    let manualSelection = false;
    const livePaths: string[] = [];
    const startupPath = runningPath === undefined ? 'C:/latest.toml' : runningPath ?? 'none';
    await page.route('**/realtime/config', route => route.fulfill({json: runningPath === undefined ? null : {
        camera_node_config: {charuco_tracking_enabled: false, skeleton_tracking_enabled: true},
        aggregator_config: {calibration_toml_path: runningPath, triangulation_enabled: true, filter_enabled: true},
    }}));
    await page.route('http://localhost:53117/freemocap/realtime/apply', route => {
        livePaths.push(route.request().postDataJSON().realtimeConfig.aggregator_config.calibration_toml_path);
        return route.fulfill({json: {camera_group_id: 'cameras', pipeline_id: 'live'}});
    });
    await page.route('http://localhost:53117/freemocap/calibration/most-recent', route => {
        discoveries += 1;
        return route.fulfill({json: manualSelection ? 'C:/replacement.toml' : 'C:/latest.toml'});
    });
    await page.route('http://localhost:53117/', route => route.fulfill({contentType: 'text/html', body: '<div id="root"></div>'}));
    await page.goto('http://localhost:53117/');
    const bundle = await build({
        stdin: {contents: `
            import React from 'react';
            import {createRoot} from 'react-dom/client';
            import {Provider} from 'react-redux';
            import {store, useAppSelector} from './src/store';
            import {wsConnectionChanged} from './src/store/slices/connection/connection-slice';
            import {loadMostRecentCalibration} from './src/store/slices/calibration';
            import {useCalibrationTomlLoader} from './src/components/viewport3d/hooks/useCalibrationTomlLoader';
            import DropdownButton from './src/components/ui-components/DropdownButton';
            store.dispatch(wsConnectionChanged(true));
            store.dispatch({type: 'realtime/apply/fulfilled', payload: {camera_group_id: 'cameras', pipeline_id: 'live'},
                meta: {arg: store.getState().realtime.pipelineConfig}});
            function Harness() {
                useCalibrationTomlLoader(true);
                const path = useAppSelector(state => state.calibration.loadedCalibration?.path ?? 'none');
                return <><output aria-label="Calibration">{path}</output>
                    <DropdownButton buttonProps={{text: 'Set up calibration', rightSideIcon: 'dropdown'}}
                        dropdownItems={<button onClick={() => store.dispatch(loadMostRecentCalibration())}>Load most recent calibration TOML (default)</button>}/>
                </>;
            }
            createRoot(document.getElementById('root')!).render(<Provider store={store}><Harness/></Provider>);
        `, resolveDir: path.resolve('.'), loader: 'tsx'},
        bundle: true, write: false, outdir: 'calibration-default-test-bundle', format: 'esm', jsx: 'automatic',
        loader: {'.yaml': 'text'}, alias: {'@': path.resolve('src')},
        plugins: [{name: 'desktop-calibration-reader', setup(builder) {
            builder.onLoad({filter: /electron-ipc\.ts$/}, () => ({contents: `
                export const electronIpc = {fileSystem: {readCalibrationToml: {query: async ({path}: {path: string}) => ({path, cameras: [], metadata: null, mtimeMs: 1})}}};
            `, loader: 'ts'}));
        }}],
    });
    for (const file of bundle.outputFiles) {
        if (file.path.endsWith('.css')) await page.addStyleTag({content: file.text});
        else await page.addScriptTag({content: file.text, type: 'module'});
    }
    await expect(page.getByLabel('Calibration', {exact: true})).toHaveText(startupPath);
    expect(discoveries).toBe(runningPath === undefined ? 1 : 0);
    expect(livePaths).toEqual([]);
    await page.reload();
    for (const file of bundle.outputFiles) {
        if (file.path.endsWith('.css')) await page.addStyleTag({content: file.text});
        else await page.addScriptTag({content: file.text, type: 'module'});
    }
    await expect(page.getByLabel('Calibration', {exact: true})).toHaveText(startupPath);
    expect(discoveries).toBe(runningPath === undefined ? 2 : 0);
    expect(livePaths).toEqual([]);
    const dropdown = page.getByRole('button', {name: 'Set up calibration', exact: true});
    await expect(dropdown.locator('svg')).toBeVisible();
    await dropdown.click();
    manualSelection = true;
    await page.getByRole('button', {name: 'Load most recent calibration TOML (default)', exact: true}).click();
    await expect(page.getByLabel('Calibration', {exact: true})).toHaveText('C:/replacement.toml');
    expect(discoveries).toBe(runningPath === undefined ? 3 : 1);
    await expect.poll(() => livePaths).toEqual(['C:/replacement.toml']);
});

}
