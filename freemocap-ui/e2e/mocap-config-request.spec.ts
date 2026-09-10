import {test, expect} from '@playwright/test';
import {build} from 'esbuild';
import path from 'node:path';

test.use({channel: process.env.PLAYWRIGHT_CHANNEL});

test('recording and processing requests carry enabled alignment and custom transforms', async ({page}) => {
    page.on('pageerror', error => {throw error;});
    const requests: {mocapTaskConfig: {
        bodyAlignment: {enabled: boolean; additional_transform: {matrix: number[]} | null};
        filterConfig: {enabled: boolean; method: string; cutoff: number; order: number};
    }}[] = [];
    await page.route('http://localhost:53117/**', async route => {
        requests.push(route.request().postDataJSON());
        await route.fulfill({json: {success: true}, headers: {'Access-Control-Allow-Origin': '*'}});
    });
    await page.route('http://localhost:53117/', route => route.fulfill({contentType: 'text/html', body: '<output id="result"></output>'}));
    await page.goto('http://localhost:53117/');
    const bundle = await build({
        stdin: {contents: `
            import {store} from './src/store/store';
            import {bodyAlignmentUpdated, referenceTransformUpdated, referenceTransformEnabledUpdated, posthocFilterConfigUpdated} from './src/store/slices/mocap/mocap-slice';
            import {activeRecordingSet} from './src/store/slices/active-recording/active-recording-slice';
            import {startMocapRecording, stopMocapRecording, processMocapRecording} from './src/store/slices/mocap/mocap-thunks';
            async function run(): Promise<void> {
                store.dispatch(activeRecordingSet({baseDirectory: 'C:/recordings', recordingName: 'sample', origin: 'browsed'}));
                store.dispatch(referenceTransformUpdated([0,-1,0,125,1,0,0,-80,0,0,1,42,0,0,0,1]));
                for (const enabled of [true, false]) {
                    store.dispatch(referenceTransformEnabledUpdated(enabled));
                    store.dispatch(bodyAlignmentUpdated(enabled));
                    store.dispatch(posthocFilterConfigUpdated({enabled, cutoff: 4.5, order: 3}));
                    await store.dispatch(startMocapRecording()).unwrap();
                    await store.dispatch(stopMocapRecording()).unwrap();
                    await store.dispatch(processMocapRecording()).unwrap();
                }
                document.getElementById('result')!.textContent = 'done';
            }
            void run().catch((error: unknown) => {document.getElementById('result')!.textContent = String(error); throw error;});
        `, resolveDir: path.resolve('.'), loader: 'ts'},
        bundle: true, write: false, outdir: 'mocap-request-test-bundle', format: 'esm',
        loader: {'.yaml': 'text'},
        alias: {'@': path.resolve('src')},
    });
    for (const file of bundle.outputFiles) {
        if (file.path.endsWith('.css')) await page.addStyleTag({content: file.text});
        else await page.addScriptTag({content: file.text, type: 'module'});
    }
    await expect(page.locator('#result')).toHaveText('done');
    expect(requests).toHaveLength(6);
    for (const request of requests.slice(0, 3)) {
        expect(request.mocapTaskConfig.filterConfig).toEqual({enabled: true, method: 'butter_low_pass', cutoff: 4.5, order: 3});
        expect(request.mocapTaskConfig.bodyAlignment).toEqual({enabled: true, additional_transform: {matrix: [0,-1,0,125,1,0,0,-80,0,0,1,42,0,0,0,1]}});
    }
    for (const request of requests.slice(3)) {
        expect(request.mocapTaskConfig.filterConfig).toEqual({enabled: false, method: 'butter_low_pass', cutoff: 4.5, order: 3});
        expect(request.mocapTaskConfig.bodyAlignment).toEqual({enabled: false, additional_transform: null});
    }
});

