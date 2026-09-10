import {test, expect} from '@playwright/test';
import {build} from 'esbuild';
import path from 'node:path';

test.use({channel: process.env.PLAYWRIGHT_CHANNEL});

test('displayed calibration owns recording and live requests, including clearing and load races', async ({page}) => {
    page.on('pageerror', error => {throw error;});
    const requests: {mocapTaskConfig?: {calibrationTomlPath: string | null}; realtimeConfig?: {aggregator_config: {calibration_toml_path: string | null}}}[] = [];
    await page.route('http://localhost:53117/**', async route => {
        requests.push(route.request().postDataJSON());
        await route.fulfill({json: {success: true, camera_group_id: 'cameras', pipeline_id: 'live'}});
    });
    await page.route('http://localhost:53117/', route => route.fulfill({contentType: 'text/html', body: '<output id="result"></output>'}));
    await page.goto('http://localhost:53117/');
    const bundle = await build({
        stdin: {contents: `
            import {store} from './src/store/store';
            import {calibrationLoadedFromBundle, loadCalibrationToml, loadCalibrationForRecording} from './src/store/slices/calibration';
            import {activeRecordingSet} from './src/store/slices/active-recording/active-recording-slice';
            import {startMocapRecording, stopMocapRecording, processMocapRecording} from './src/store/slices/mocap/mocap-thunks';
            import {applyRealtimePipeline, closePipeline} from './src/store/slices/realtime/realtime-thunks';
            function assert(value: boolean, message: string): void {if (!value) throw new Error(message);}
            function settled(): Promise<void> {
                if (!store.getState().realtime.isLoading) return Promise.resolve();
                return new Promise(resolve => {
                    const unsubscribe = store.subscribe(() => {
                        if (!store.getState().realtime.isLoading) {unsubscribe(); resolve();}
                    });
                });
            }
            async function run(): Promise<void> {
                const selected = {path: 'C:/selected.toml', cameras: [], metadata: null, mtimeMs: 1};
                store.dispatch(calibrationLoadedFromBundle(selected));
                store.dispatch(activeRecordingSet({baseDirectory: 'C:/recordings', recordingName: 'sample', origin: 'browsed'}));
                for (const thunk of [startMocapRecording, stopMocapRecording, processMocapRecording]) await store.dispatch(thunk()).unwrap();
                const config = store.getState().realtime.pipelineConfig;
                await store.dispatch(applyRealtimePipeline({...config, aggregator_config: {...config.aggregator_config, calibration_toml_path: 'C:/stale.toml'}})).unwrap();
                store.dispatch(calibrationLoadedFromBundle({...selected, path: 'C:/replacement.toml'}));
                await settled();
                store.dispatch(calibrationLoadedFromBundle(null));
                await settled();
                store.dispatch(closePipeline.fulfilled(undefined, 'close', undefined));
                store.dispatch(calibrationLoadedFromBundle(selected));
                store.dispatch(loadCalibrationToml.pending('older', {path: 'C:/older.toml'}));
                store.dispatch(loadCalibrationToml.pending('newer', {path: 'C:/newer.toml'}));
                const pendingRequest = await store.dispatch(processMocapRecording());
                assert(processMocapRecording.rejected.match(pendingRequest), 'Processing must reject a pending calibration');
                store.dispatch(loadCalibrationToml.fulfilled({...selected, path: 'C:/older.toml'}, 'older', {path: 'C:/older.toml'}));
                assert(store.getState().calibration.loadedCalibration?.path === selected.path, 'Stale load changed selection');
                store.dispatch(loadCalibrationToml.rejected(new Error('Unreadable TOML'), 'newer', {path: 'C:/newer.toml'}));
                assert(store.getState().calibration.loadedCalibration === null, 'Failed load retained geometry');
                assert(Boolean(store.getState().calibration.error), 'Failed load was hidden');
                store.dispatch(calibrationLoadedFromBundle(selected));
                store.dispatch(loadCalibrationForRecording.pending('empty', {recordingId: 'empty'}));
                store.dispatch(loadCalibrationForRecording.fulfilled(null, 'empty', {recordingId: 'empty'}));
                assert(store.getState().calibration.loadedCalibration === null, 'Missing recording calibration retained geometry');
                document.getElementById('result')!.textContent = 'done';
            }
            void run().catch((error: unknown) => {document.getElementById('result')!.textContent = String(error); throw error;});
        `, resolveDir: path.resolve('.'), loader: 'ts'},
        bundle: true, write: false, outdir: 'calibration-selection-test-bundle', format: 'esm',
        loader: {'.yaml': 'text'}, alias: {'@': path.resolve('src')},
    });
    for (const file of bundle.outputFiles) {
        if (file.path.endsWith('.css')) await page.addStyleTag({content: file.text});
        else await page.addScriptTag({content: file.text, type: 'module'});
    }
    await expect(page.locator('#result')).toHaveText('done');
    expect(requests.slice(0, 3).map(request => request.mocapTaskConfig?.calibrationTomlPath)).toEqual(Array(3).fill('C:/selected.toml'));
    expect(requests.slice(3).map(request => request.realtimeConfig?.aggregator_config.calibration_toml_path)).toEqual(['C:/selected.toml', 'C:/replacement.toml', null]);
});

test('opening calibration options and automatic discovery preserve the selected file', async ({page}) => {
    page.on('pageerror', error => {throw error;});
    await page.route('http://localhost:53117/**', route => route.fulfill({json: {
        recording_path: 'C:/folder.toml',
    }}));
    await page.route('**/calibration/most-recent', route => route.fulfill({json: 'C:/recent.toml'}));
    await page.route('http://localhost:53117/', route => route.fulfill({contentType: 'text/html', body: '<div id="root"></div>'}));
    await page.goto('http://localhost:53117/');
    const bundle = await build({
        stdin: {contents: `
            import React, {useState} from 'react';
            import {createRoot} from 'react-dom/client';
            import {Provider} from 'react-redux';
            import {store, useAppSelector} from './src/store';
            import {calibrationLoadedFromBundle} from './src/store/slices/calibration';
            import {activeRecordingSet} from './src/store/slices/active-recording/active-recording-slice';
            import {RecordingCalibrationOptions} from './src/components/mocap-setup/RecordingCalibrationOptions';
            import {useCalibrationTomlLoader} from './src/components/viewport3d/hooks/useCalibrationTomlLoader';
            store.dispatch(calibrationLoadedFromBundle({path: 'C:/selected.toml', cameras: [], metadata: null, mtimeMs: 1}));
            store.dispatch(activeRecordingSet({baseDirectory: 'C:/recordings', recordingName: 'sample', origin: 'browsed'}));
            function Harness() {
                const [open, setOpen] = useState(true);
                useCalibrationTomlLoader(true);
                const selected = useAppSelector(state => state.calibration.loadedCalibration?.path ?? 'none');
                return <><output aria-label="Selected calibration">{selected}</output>
                    <button onClick={() => setOpen(!open)}>Toggle options</button>
                    {open && <RecordingCalibrationOptions/>}</>;
            }
            createRoot(document.getElementById('root')!).render(<Provider store={store}><Harness/></Provider>);
        `, resolveDir: path.resolve('.'), loader: 'tsx'},
        bundle: true, write: false, outdir: 'calibration-options-test-bundle', format: 'esm', jsx: 'automatic',
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
    const folderButton = page.getByRole('button', {name: "Use this recording's calibration"});
    await expect(folderButton).toBeEnabled();
    await expect(page.getByLabel('Selected calibration')).toHaveText('C:/selected.toml');
    await page.getByRole('button', {name: 'Toggle options'}).click();
    await page.getByRole('button', {name: 'Toggle options'}).click();
    await expect(folderButton).toBeEnabled();
    await expect(page.getByLabel('Selected calibration')).toHaveText('C:/selected.toml');
    await folderButton.click();
    await expect(page.getByLabel('Selected calibration')).toHaveText('C:/folder.toml');
    await page.getByRole('button', {name: 'Use most recent calibration'}).click();
    await expect(page.getByLabel('Selected calibration')).toHaveText('C:/recent.toml');
});
