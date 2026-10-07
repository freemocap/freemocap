import {test, expect, type Page} from '@playwright/test';
import {build} from 'esbuild';
import path from 'node:path';
import {calibrationFixture} from './fixtures/calibration';

test.use({channel: process.env.PLAYWRIGHT_CHANNEL});

async function mount(page: Page, beforeContent?: (path: string) => Promise<void>): Promise<void> {
    page.on('pageerror', error => {throw error;});
    await page.route('**/calibration/content?*', async route => {
        const selected = new URL(route.request().url()).searchParams.get('path')!;
        await beforeContent?.(selected);
        await route.fulfill({json: calibrationFixture(selected)});
    });
    await page.route('http://localhost:53117/', route => route.fulfill({contentType: 'text/html', body: '<div id="root"></div>'}));
    await page.goto('http://localhost:53117/');
    const bundle = await build({
        stdin: {contents: `
            import React, {useState} from 'react';
            import {createRoot} from 'react-dom/client';
            import {Provider} from 'react-redux';
            import {store, useAppSelector} from './src/store';
            import {useRecordingCalibrationDefault} from './src/hooks/useRecordingCalibrationDefault';
            import {calibrationLoadedFromBundle, loadCalibrationToml} from './src/store/slices/calibration';
            import {activeRecordingSet} from './src/store/slices/active-recording/active-recording-slice';
            import {processMocapRecording} from './src/store/slices/mocap/mocap-thunks';
            import {calibrationFixture} from './e2e/fixtures/calibration';
            const selectRecording = recordingName => store.dispatch(activeRecordingSet({
                baseDirectory: 'C:/recordings', recordingName, origin: 'browsed',
            }));
            selectRecording('first');
            store.dispatch(calibrationLoadedFromBundle(calibrationFixture('C:/previous.toml')));
            function DefaultLoader() {useRecordingCalibrationDefault(); return null;}
            function Harness() {
                const [open, setOpen] = useState(true);
                const calibration = useAppSelector(state => state.calibration);
                return <>
                    {open && <DefaultLoader/>}
                    <output aria-label="Selected">{calibration.loadedCalibration?.path ?? 'none'}</output>
                    <output aria-label="Pending">{calibration.loadRequestId ? 'yes' : 'no'}</output>
                    <output aria-label="Error">{calibration.error ?? ''}</output>
                    <button onClick={() => setOpen(!open)}>Toggle panel</button>
                    <button onClick={() => store.dispatch(loadCalibrationToml({path: 'C:/manual.toml'}))}>Manual</button>
                    <button onClick={() => store.dispatch(calibrationLoadedFromBundle(null))}>Clear</button>
                    <button onClick={() => selectRecording('second')}>Second recording</button>
                    <button onClick={() => selectRecording('first')}>First recording</button>
                    <button onClick={() => store.dispatch(processMocapRecording())}>Process</button>
                </>;
            }
            createRoot(document.getElementById('root')!).render(<React.StrictMode><Provider store={store}><Harness/></Provider></React.StrictMode>);
        `, resolveDir: path.resolve('.'), loader: 'tsx'},
        bundle: true, write: false, outdir: 'recording-calibration-test-bundle', format: 'esm', jsx: 'automatic',
        loader: {'.yaml': 'text'}, alias: {'@': path.resolve('src')},
    });
    for (const file of bundle.outputFiles) {
        if (file.path.endsWith('.css')) await page.addStyleTag({content: file.text});
        else await page.addScriptTag({content: file.text, type: 'module'});
    }
}

test('recording calibration defaults on load and recording changes; overrides survive reopening', async ({page}) => {
    const discoveries: string[] = [];
    const processing: string[] = [];
    await page.route('**/calibration/files?*', route => {
        const directory = new URL(route.request().url()).searchParams.get('recording_directory')!;
        discoveries.push(directory);
        return route.fulfill({json: {recording_path: `${directory}/camera_calibration.toml`}});
    });
    await page.route('**/mocap/recording/process', route => {
        processing.push(route.request().postDataJSON().mocapTaskConfig.calibrationTomlPath);
        return route.fulfill({json: {success: true}});
    });
    await mount(page);
    await expect(page.getByLabel('Selected')).toHaveText('C:/recordings/first/camera_calibration.toml');
    await page.getByRole('button', {name: 'Process', exact: true}).click();
    await expect.poll(() => processing).toEqual(['C:/recordings/first/camera_calibration.toml']);
    await page.getByRole('button', {name: 'Manual', exact: true}).click();
    await expect(page.getByLabel('Selected')).toHaveText('C:/manual.toml');
    await page.getByRole('button', {name: 'Toggle panel'}).click();
    await page.getByRole('button', {name: 'Toggle panel'}).click();
    await expect(page.getByLabel('Selected')).toHaveText('C:/manual.toml');
    expect(discoveries).toEqual(['C:/recordings/first']);
    await page.getByRole('button', {name: 'Second recording'}).click();
    await expect(page.getByLabel('Selected')).toHaveText('C:/recordings/second/camera_calibration.toml');
    await page.getByRole('button', {name: 'First recording'}).click();
    await expect(page.getByLabel('Selected')).toHaveText('C:/recordings/first/camera_calibration.toml');
});

for (const outcome of ['missing', 'error']) {
    test(`${outcome} calibration discovery is handled visibly`, async ({page}) => {
        await page.route('**/calibration/files?*', route => route.fulfill(outcome === 'missing'
            ? {json: {recording_path: null}} : {status: 400, json: {detail: 'Multiple calibration files; select a TOML explicitly'}}));
        await mount(page);
        await expect(page.getByLabel('Pending')).toHaveText('no');
        await expect(page.getByLabel('Selected')).toHaveText(outcome === 'missing' ? 'C:/previous.toml' : 'none');
        if (outcome === 'error') await expect(page.getByLabel('Error')).toContainText('Multiple calibration files');
    });
}

for (const stage of ['discovery', 'content']) {
    for (const override of ['Manual', 'Clear', 'Second recording']) {
        test(`${override} wins over delayed ${stage}`, async ({page}) => {
            let release!: () => void;
            const gate = new Promise<void>(resolve => {release = resolve;});
            let waiting = false;
            await page.route('**/calibration/files?*', async route => {
                const directory = new URL(route.request().url()).searchParams.get('recording_directory')!;
                if (stage === 'discovery' && directory.endsWith('/first')) {waiting = true; await gate;}
                await route.fulfill({json: {recording_path: `${directory}/camera_calibration.toml`}});
            });
            await mount(page, async selected => {
                if (stage === 'content' && selected.includes('/first/')) {waiting = true; await gate;}
            });
            await expect.poll(() => waiting).toBe(true);
            await page.getByRole('button', {name: override, exact: true}).click();
            const expected = override === 'Manual' ? 'C:/manual.toml' : override === 'Clear' ? 'none'
                : 'C:/recordings/second/camera_calibration.toml';
            await expect(page.getByLabel('Selected')).toHaveText(expected);
            const response = page.waitForResponse(url => stage === 'discovery'
                ? url.url().includes('/calibration/files?') && url.url().includes('first')
                : url.url().includes('/calibration/content?') && url.url().includes('first'));
            release();
            await response;
            await expect(page.getByLabel('Pending')).toHaveText('no');
            await expect(page.getByLabel('Selected')).toHaveText(expected);
        });
    }
}
