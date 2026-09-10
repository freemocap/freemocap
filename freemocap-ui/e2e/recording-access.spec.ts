import {test, expect} from '@playwright/test';
import {build} from 'esbuild';
import path from 'node:path';

test.use({channel: process.env.PLAYWRIGHT_CHANNEL});

test('late bundle responses cannot restore invalidated recording data', async ({page}) => {
    await page.setContent('<output id="result"></output>');
    const bundle = await build({
        stdin: {resolveDir: path.resolve('.'), loader: 'ts', contents: `
            import {playbackDataSlice, fetchPlaybackBundle, recordingPlaybackInvalidated} from './src/store/slices/playback-data/playback-data-slice';
            const location = {recordingId: 'recording', recordingParentDirectory: 'C:/recordings'};
            const reduce = playbackDataSlice.reducer;
            const pending = reduce(undefined, fetchPlaybackBundle.pending('first', location));
            const invalidated = reduce(pending, recordingPlaybackInvalidated(location));
            const stale = reduce(invalidated, fetchPlaybackBundle.fulfilled({recordingId: 'stale'}, 'first', location));
            if (Object.values(stale.byRecordingId)[0].bundle !== null) throw new Error('Stale bundle reopened recording');
            const loading = reduce(stale, fetchPlaybackBundle.pending('second', location));
            const fresh = reduce(loading, fetchPlaybackBundle.fulfilled({recordingId: 'fresh'}, 'second', location));
            if (Object.values(fresh.byRecordingId)[0].bundle?.recordingId !== 'fresh') throw new Error('Fresh bundle was discarded');
            document.getElementById('result')!.textContent = 'passed';
        `},
        bundle: true, write: false, format: 'esm', alias: {'@': path.resolve('src')},
        plugins: [{name: 'http-boundary', setup(builder) {
            builder.onResolve({filter: /^@\/services$/}, () => ({path: 'http', namespace: 'http'}));
            builder.onLoad({filter: /.*/, namespace: 'http'}, () => ({contents: 'export const serverUrls = {};', loader: 'ts'}));
        }}],
    });
    await page.addScriptTag({content: bundle.outputFiles[0].text, type: 'module'});
    await expect(page.locator('#result')).toHaveText('passed');
});

test('recording ownership unmounts playback and release restores the session', async ({page}) => {
    const errors: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.setContent('<div id="root" style="height:720px"></div>');
    await page.addStyleTag({path: path.resolve('src/styles/App.css')});
    await page.addStyleTag({path: path.resolve('src/styles/color.css')});
    await page.addStyleTag({path: path.resolve('src/styles/reset.css')});
    const bundle = await build({
        stdin: {resolveDir: path.resolve('.'), loader: 'tsx', contents: `
            import React from 'react';
            import {createRoot} from 'react-dom/client';
            import PlaybackPage from './src/pages/PlaybackPage';
            import {setOwners} from '@/store';
            Object.assign(window, {setOwners});
            createRoot(document.getElementById('root')!).render(<PlaybackPage />);
        `},
        bundle: true, write: false, format: 'esm', alias: {'@': path.resolve('src')},
        plugins: [{name: 'playback-boundaries', setup(builder) {
            builder.onResolve({filter: /^@\/store(?:\/.*)?$/}, () => ({path: 'state', namespace: 'state'}));
            builder.onLoad({filter: /.*/, namespace: 'state'}, () => ({loader: 'ts', resolveDir: path.resolve('.'), contents: `
                import {useSyncExternalStore} from 'react';
                let state = {pipelines: {activePipelines: {}, recordingOwners: []}};
                const listeners = new Set<() => void>();
                const dispatch = () => ({unwrap: () => Promise.resolve(), abort: () => {}});
                export const useAppDispatch = () => dispatch;
                export const useAppSelector = (selector) => selector(useSyncExternalStore(
                    callback => {listeners.add(callback); return () => listeners.delete(callback);}, () => state));
                export const setOwners = (owners) => {state = {pipelines: {activePipelines: {}, recordingOwners: owners}}; listeners.forEach(callback => callback());};
                export const selectActiveRecordingName = () => 'recording';
                export const selectActiveRecordingBaseDirectory = () => 'C:/recordings';
                export const selectActiveRecordingFullPath = () => 'C:/recordings/recording';
                export const selectPlaybackBundle = () => () => ({});
                export const selectPlaybackBundleError = () => () => null;
                export const fetchTaskSnapshot = () => ({}), fetchPlaybackBundle = () => ({});
            `}));
            builder.onResolve({filter: /RecordingPlaybackSession$/}, () => ({path: 'session', namespace: 'session'}));
            builder.onLoad({filter: /.*/, namespace: 'session'}, () => ({loader: 'tsx', resolveDir: path.resolve('.'), contents: `
                import React, {useEffect} from 'react';
                export default function Session() {
                    useEffect(() => {window.opened = (window.opened ?? 0) + 1; return () => {window.closedCount = (window.closedCount ?? 0) + 1;};}, []);
                    return <div className="flex-1 min-h-0" data-testid="session">Playback session</div>;
                }
            `}));
            builder.onResolve({filter: /server-context$/}, () => ({path: 'server', namespace: 'server'}));
            builder.onLoad({filter: /.*/, namespace: 'server'}, () => ({contents: 'export const useServer = () => ({isConnected: true});', loader: 'ts'}));
        }}],
    });
    await page.addScriptTag({content: bundle.outputFiles[0].text, type: 'module'});
    await expect(page.getByTestId('session')).toBeVisible();
    expect((await page.getByTestId('session').boundingBox())!.height).toBe(720);
    await page.evaluate(() => (window as unknown as {setOwners: (owners: object[]) => void}).setOwners([
        {task_id: 'task', recording: {full_path: 'c:/recordings/recording'}},
    ]));
    await expect(page.getByTestId('session')).toHaveCount(0);
    await expect(page.getByRole('status')).toContainText('being processed');
    await page.screenshot({path: 'test-results/playback-processing-state.png'});
    expect(await page.evaluate(() => (window as unknown as {closedCount: number}).closedCount)).toBe(1);
    await page.evaluate(() => (window as unknown as {setOwners: (owners: object[]) => void}).setOwners([]));
    await expect(page.getByTestId('session')).toBeVisible();
    expect(await page.evaluate(() => (window as unknown as {opened: number}).opened)).toBe(2);
    await page.locator('#root').evaluate(element => {element.style.height = '480px';});
    expect((await page.getByTestId('session').boundingBox())!.height).toBe(480);
    expect(errors).toEqual([]);
});

