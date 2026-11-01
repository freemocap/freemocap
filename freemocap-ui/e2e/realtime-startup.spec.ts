import {test, expect, type Page} from '@playwright/test';
import {build} from 'esbuild';
import {resolve} from 'node:path';
import {execFileSync} from 'node:child_process';

test.use({channel: process.env.PLAYWRIGHT_CHANNEL || undefined});

async function mountPipeline(page: Page) {
    // Isolated page: every request is intercepted, including calibration and cameras.
    await page.route('**/*', route => route.fulfill({contentType: 'text/html', body: '<div id="root"></div>'}));
    await page.goto('https://realtime-startup.test/');
    const bundle = await build({stdin: {contents: `
        import React from 'react';
        import {createRoot} from 'react-dom/client';
        import {Provider} from 'react-redux';
        import {store} from './src/store/store';
        import {applyRealtimePipeline, pipelineConfigUpdated} from './src/store/slices/realtime';
        import {loadRealtimeCalibrationDefault} from './src/store/slices/calibration/calibration-thunks';
        import {OperationErrorBanner} from './src/components/common/OperationErrorBanner';
        import CalibrationReferenceFrame from './src/components/pipeline-progress/calibration-progress/calibration-reference-frame';
        import {getDetailedErrorMessage} from './src/store/slices/thunk-helpers';
        const calibration = {path: 'selected-calibration.toml', metadata: {board: {
            squares_x: 7, squares_y: 5, square_length_mm: 42,
            marker_length_ratio: 0.8, aruco_dictionary_enum: 0,
        }}};
        store.dispatch(loadRealtimeCalibrationDefault.pending('test-calibration', undefined));
        store.dispatch(loadRealtimeCalibrationDefault.fulfilled(calibration, 'test-calibration', undefined));
        window.readConfig = () => store.getState().realtime.pipelineConfig;
        window.applyConfig = async (detector) => {
            const config = structuredClone(window.readConfig());
            config.camera_node_config.detector_type = detector;
            config.camera_node_config.mediapipe_detection_confidence = 0.65;
            // Reproduce a resolved server recipe retained by an already-open UI.
            config.camera_node_config.skeleton_tracker_config = {stages: [{
                bbox_smoothing: {alpha: 0.4}, children: [{
                    object_detector: {detector_type: 'keypoint_bbox', session_backend: 'cpu'},
                    bbox_smoothing: {alpha: 0.4},
                }],
            }]};
            config.camera_node_config.charuco_tracker_config = {stages: []};
            store.dispatch(pipelineConfigUpdated(config));
            window.updatedConfig = window.readConfig();
            return store.dispatch(applyRealtimePipeline(config));
        };
        window.formatError = (body, status, statusText) => getDetailedErrorMessage(new Response(body, {status, statusText}));
        createRoot(document.getElementById('root')).render(<Provider store={store}>
            <OperationErrorBanner /><CalibrationReferenceFrame calibrationPath={calibration.path} />
        </Provider>);
    `, loader: 'tsx', resolveDir: resolve('.')}, bundle: true, write: false,
        format: 'esm', outdir: 'realtime-test-bundle', loader: {'.yaml': 'text'}, alias: {'@': resolve('src')}});
    for (const file of bundle.outputFiles) {
        if (file.path.endsWith('.css')) await page.addStyleTag({content: file.text});
        else await page.addScriptTag({content: file.text, type: 'module'});
    }
}

test('Apply sends selected settings without replaying generated tracker recipes', async ({page}) => {
    test.setTimeout(60000);
    await mountPipeline(page);
    let request: any;
    await page.route('**/freemocap/realtime/apply', async route => {
        request = route.request().postDataJSON();
        // The server response contains derived configuration; it must not become editable settings.
        await route.fulfill({json: {camera_group_id: 'test-cameras', pipeline_id: 'test-pipeline',
            resolved_config: {...request.realtimeConfig, camera_node_config: {
                ...request.realtimeConfig.camera_node_config,
                skeleton_tracker_config: {stages: []}, charuco_tracker_config: {stages: []},
            }}}});
    });
    for (const detector of ['rtmw_mediapipe_hands', 'mediapipe', 'rtmpose']) {
        const result = await page.evaluate(detector => (window as any).applyConfig(detector), detector);
        expect(result.type).toBe('realtime/apply/fulfilled');
        const settings = request.realtimeConfig.camera_node_config;
        expect(settings).not.toHaveProperty('skeleton_tracker_config');
        expect(settings).not.toHaveProperty('charuco_tracker_config');
        expect(settings.detector_type).toBe(detector);
        expect(settings.mediapipe_detection_confidence).toBe(0.65);
        expect(settings.charuco_board.square_length_mm).toBe(42);
        expect(request.realtimeConfig.aggregator_config.calibration_toml_path).toBe('selected-calibration.toml');
        const restored = await page.evaluate(() => (window as any).readConfig().camera_node_config);
        expect(restored).not.toHaveProperty('skeleton_tracker_config');
        expect(restored).not.toHaveProperty('charuco_tracker_config');
        const updated = await page.evaluate(() => (window as any).updatedConfig.camera_node_config);
        expect(updated).not.toHaveProperty('skeleton_tracker_config');
        expect(updated).not.toHaveProperty('charuco_tracker_config');
        // Validate the actual browser-generated body using the backend's request model.
        // This imports configuration only; no app, camera or inference worker is started.
        const python = process.env.FREEMOCAP_PYTHON ?? resolve(process.platform === 'win32'
            ? '../.venv/Scripts/python.exe' : '../.venv/bin/python');
        execFileSync(python, ['-B', '-c', `
import json,sys
from freemocap.api.http.realtime.realtime_router import RealtimePipelineConnectRequest
request = RealtimePipelineConnectRequest.model_validate(json.load(sys.stdin))
camera = request.realtime_config.camera_node_config
assert camera.charuco_board.square_length_mm == 42
assert camera.mediapipe_detection_confidence == 0.65
if camera.detector_type != 'rtmpose':
    hands = [child for child in camera.skeleton_tracker_config.stages[0].children if child.name.endswith('_hand')]
    assert len(hands) == 2
    assert all(hand.object_detector.scale_factor == 3.0 for hand in hands)
    assert all(hand.object_detector.center_keypoint_names for hand in hands)
    assert all(hand.bbox_smoothing.min_cutoff > 0 for hand in hands)
`], {cwd: resolve('..'), input: JSON.stringify(request), timeout: 20000});
    }
});

test('validation failures show field paths and messages in the actual error banner', async ({page}) => {
    await mountPipeline(page);
    await page.route('**/freemocap/realtime/apply', route => route.fulfill({status: 422, json: {detail: [
        {type: 'missing', loc: ['body', 'realtimeConfig', 'camera_node_config', 'skeleton_tracker_config', 'stages', 0, 'children', 0, 'object_detector', 'center_keypoint_names'], msg: 'Field required'},
        {type: 'extra_forbidden', loc: ['body', 'realtimeConfig', 'camera_node_config', 'skeleton_tracker_config', 'stages', 0, 'bbox_smoothing', 'alpha'], msg: 'Extra inputs are not permitted'},
    ]}}));
    await page.evaluate(() => (window as any).applyConfig('rtmw_mediapipe_hands'));
    const banner = page.locator('.operation-error-banner');
    await expect(banner).toContainText('HTTP 422');
    await expect(banner).toContainText('center_keypoint_names: Field required');
    await expect(banner).toContainText('bbox_smoothing.alpha: Extra inputs are not permitted');
    await expect(banner).not.toContainText('[object Object]');
    const calibrationError = page.locator('[aria-label="Streaming calibration reference frame"]').getByRole('alert');
    await expect(calibrationError).toContainText('center_keypoint_names: Field required');
    await expect(calibrationError).not.toContainText('[object Object]');
    await expect(calibrationError).toHaveCSS('white-space', 'pre-wrap');
    const textError = await page.evaluate(() => (window as any).formatError('Server unavailable', 503, 'Service Unavailable'));
    expect(textError).toContain('Server unavailable');
    for (const [body, expected] of [
        ['{"detail":"Calibration file is missing"}', 'Calibration file is missing'],
        ['{"error":{"message":"Camera connection failed"}}', 'Camera connection failed'],
        ['{"reason":"Unexpected server failure"}', 'Unexpected server failure'],
        ['', 'HTTP 500: Internal Server Error'],
    ]) {
        const message = await page.evaluate(body =>
            (window as any).formatError(body, 500, 'Internal Server Error'), body);
        expect(message).toContain(expected);
        expect(message).not.toContain('[object Object]');
    }
});
