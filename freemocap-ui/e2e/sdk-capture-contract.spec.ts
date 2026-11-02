import {test, expect} from '@playwright/test';
import {build} from 'esbuild';
import path from 'node:path';

test.use({channel: process.env.PLAYWRIGHT_CHANNEL});

test('SDK preserves distinct calibration capture, stop and processing request contracts', async ({page}) => {
    const requests: {path: string; body: Record<string, unknown>}[] = [];
    await page.route('http://localhost:53117/**', async route => {
        if (route.request().method() === 'POST') {
            requests.push({path: new URL(route.request().url()).pathname, body: route.request().postDataJSON()});
            await route.fulfill({json: {success: true, task_id: 'task', recording_id: 'calibration', recording_parent_directory: 'C:/recordings'}});
        } else await route.fulfill({json: {server_instance_id: '11111111-1111-4111-8111-111111111111', revision: 0, recording_owners: [], tasks: []}});
    });
    await page.route('http://localhost:53117/', route => route.fulfill({contentType: 'text/html', body: '<output id="result"></output>'}));
    await page.goto('http://localhost:53117/');
    const bundle = await build({stdin: {contents: `
        import {store} from './src/store/store';
        import {recordingDirectoryChanged} from './src/store/slices/recording/recording-slice';
        import {activeRecordingSet} from './src/store/slices/active-recording/active-recording-slice';
        import {startCalibrationRecording, stopCalibrationRecording, calibrateRecording} from './src/store/slices/calibration/calibration-thunks';
        async function run() {
            store.dispatch(recordingDirectoryChanged('C:/recordings'));
            store.dispatch(activeRecordingSet({baseDirectory: 'C:/recordings', recordingName: 'calibration', origin: 'browsed'}));
            await store.dispatch(startCalibrationRecording()).unwrap();
            await store.dispatch(stopCalibrationRecording()).unwrap();
            await store.dispatch(calibrateRecording({recordingPath:'C:/recordings/calibration'})).unwrap();
            document.getElementById('result')!.textContent = 'done';
        }
        void run().catch(error => {document.getElementById('result')!.textContent = JSON.stringify(error);});
    `, resolveDir: path.resolve('.'), loader: 'ts'}, bundle: true, write: false,
        outdir: 'sdk-capture-test-bundle', format: 'esm', loader: {'.yaml': 'text'}, alias: {'@': path.resolve('src')}});
    for (const file of bundle.outputFiles) {
        if (file.path.endsWith('.css')) await page.addStyleTag({content: file.text});
        else await page.addScriptTag({content: file.text, type: 'module'});
    }
    await expect(page.locator('#result')).toHaveText('done');
    expect(requests.map(item => item.path)).toEqual(['/freemocap/capture/calibration/start',
        '/freemocap/capture/calibration/stop', '/freemocap/recordings/calibration/processing']);
    expect(Object.keys(requests[0].body).sort()).toEqual(['calibrationRecordingDirectory', 'calibrationTaskConfig']);
    expect(requests[0].body.calibrationRecordingDirectory).toMatch(/^C:\/recordings\/.+_calibration$/);
    expect(Object.keys(requests[1].body)).toEqual(['calibrationTaskConfig']);
    expect(requests[2].body).toEqual({kind: 'calibration', config: requests[0].body.calibrationTaskConfig});
});
