// Bundle with esbuild --bundle --platform=node --format=cjs --loader:.yaml=text, then node --test.
// The store import follows the application entry order; camera/renderer APIs are never exercised.
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {getDlcReadiness, inspectDlcModel, importDlcModel, getDlcImportJob} from './dlc-models';
import {serverUrls} from '@/constants/server-urls';
import {realtimeExecutionSettings, acceptedRealtimeSettings} from '@/store/slices/realtime/realtime-settings';
import {defaultRealtimePipelineConfig} from '@/store/slices/realtime/realtime-types';
import {dlcPosthocExecutionSettings} from '@/store/slices/mocap/dlc-execution-settings';
import {DETECTOR_OPTIONS} from '@/components/mocap-setup/detector-options';

test('DLC selection projects explicit CPU/CUDA 2D execution without losing human settings', () => {
    const human = structuredClone(defaultRealtimePipelineConfig);
    human.skeleton_inference_node_config.execution_provider = 'trt';
    const requested = {...human, camera_node_config: {...human.camera_node_config, detector_type: 'dlc' as const, dlc_model_path: '/model.yaml'}};
    for (const provider of ['cpu', 'cuda'] as const) {
        const outgoing = realtimeExecutionSettings(requested, provider);
        assert.equal(outgoing.skeleton_inference_node_config.execution_provider, provider);
        assert.equal(outgoing.aggregator_config.triangulation_enabled, false);
        assert.equal(outgoing.aggregator_config.skeleton_fitting_enabled, false);
        assert.equal(outgoing.camera_node_config.charuco_tracking_enabled, false);
        assert.equal(outgoing.aggregator_config.calibration_toml_path, null);
        const accepted = acceptedRealtimeSettings(outgoing, requested);
        assert.deepEqual(accepted, requested);
        const switchedBack = {...accepted, camera_node_config: {...accepted.camera_node_config, detector_type: 'rtmpose' as const}};
        assert.deepEqual(realtimeExecutionSettings(switchedBack, provider), switchedBack);
    }
    assert.equal(human.aggregator_config.triangulation_enabled, true);
    assert.equal(requested.skeleton_inference_node_config.execution_provider, 'trt');
    assert.ok(DETECTOR_OPTIONS.some(option => option.value === 'dlc'));
});

test('DLC observation-only settings override a selected reconstruction stage and preserve run selection', () => {
    const selected = {startStage: 'triangulation', stopStage: 'reconstruction', baseRunId: 7, runSaveMode: 'new_run', graphExecutionProvider: 'auto', exportToBlender: true};
    const actual = {...selected, ...dlcPosthocExecutionSettings('dlc', 'cuda')};
    assert.equal(actual.startStage, 'observations');
    assert.equal(actual.stopStage, 'observations');
    assert.equal(actual.graphExecutionProvider, 'cuda');
    assert.equal(actual.exportToBlender, false);
    assert.equal(actual.baseRunId, 7);
    assert.equal(actual.runSaveMode, 'new_run');
    assert.deepEqual(dlcPosthocExecutionSettings('rtmpose', 'cpu'), {});
    assert.equal(selected.stopStage, 'reconstruction');
});

test('model inspection preserves arbitrary keypoint names and import polling uses server URLs', async context => {
    const names = ['hinge_tip', 'different_point', 'feature_z'];
    const metadata = {sidecar_path: '/models/custom.yaml', keypoint_names: names, connections: [['feature_z', 'hinge_tip']], input_size: [480, 640]};
    const requests: {url: string; body: unknown}[] = [];
    context.mock.method(globalThis, 'fetch', async (input: string | URL, init?: RequestInit) => {
        const url = String(input);
        requests.push({url, body: init?.body ? JSON.parse(init.body as string) : null});
        if (url.endsWith('/readiness')) return Response.json({available: false, missing_packages: ['torch'], detail: 'Configure the converter environment'});
        if (url.endsWith('/inspect')) return Response.json(metadata);
        if (url.endsWith('/import')) return Response.json({job_id: 'job1', status: 'queued', detail: 'Queued', result: null}, {status: 202});
        return Response.json({job_id: 'job1', status: 'complete', result: metadata});
    });
    assert.equal((await getDlcReadiness()).available, false);
    assert.deepEqual((await inspectDlcModel('/models/custom.yaml')).keypoint_names, names);
    const request = {pose_config_path: '/pose.yaml', checkpoint_path: '/weights.pt', project_config_path: '/project.yaml', image_height: 480, image_width: 640};
    assert.equal((await importDlcModel(request)).status, 'queued');
    assert.deepEqual((await getDlcImportJob('job1')).result?.connections, metadata.connections);
    assert.deepEqual(requests[2].body, request);
    assert.equal(requests[3].url, `${serverUrls.getHttpUrl()}/freemocap/dlc/import/job1`);
});

test('unsupported models and missing converter dependencies stay readable', async context => {
    context.mock.method(globalThis, 'fetch', async () => Response.json({detail: [{loc: ['body', 'pose_config_path'], msg: 'Unsupported DLC architecture'}]}, {status: 422}));
    await assert.rejects(inspectDlcModel('/bad.yaml'), /body.pose_config_path: Unsupported DLC architecture/);
    context.mock.method(globalThis, 'fetch', async () => Response.json({detail: 'Missing converter packages: torch'}, {status: 503}));
    await assert.rejects(getDlcReadiness(), /Missing converter packages: torch/);
});

test('live DLC applies with an unavailable calibration without requesting one', async context => {
    // Store barrels import the decoder module; this test never renders or reads cameras.
    const previousCanvas = Object.getOwnPropertyDescriptor(globalThis, 'OffscreenCanvas');
    Object.defineProperty(globalThis, 'OffscreenCanvas', {configurable: true, value: class {getContext() {return null;}}});
    context.after(() => {if (previousCanvas) Object.defineProperty(globalThis, 'OffscreenCanvas', previousCanvas); else Reflect.deleteProperty(globalThis, 'OffscreenCanvas');});
    const {store} = await import('@/store');
    const {applyRealtimePipeline} = await import('@/store/slices/realtime/realtime-thunks');
    const original = store.getState();
    const state = {...original, cameras: {...original.cameras, cameras: []}, calibration: {...original.calibration,
        loadRequestId: 'unrelated-calibration-load', loadedCalibration: null, error: 'No calibration'},
        mocap: {...original.mocap, config: {...original.mocap.config, dlcExecutionProvider: 'cpu' as const}}};
    const requested = {...defaultRealtimePipelineConfig, camera_node_config: {...defaultRealtimePipelineConfig.camera_node_config,
        detector_type: 'dlc' as const, dlc_model_path: '/model.yaml'}};
    const requests: string[] = [];
    context.mock.method(globalThis, 'fetch', async (input: string | URL, init?: RequestInit) => {
        const url = String(input);
        requests.push(url);
        const body = JSON.parse(init?.body as string);
        assert.equal(body.realtimeConfig.aggregator_config.triangulation_enabled, false);
        assert.equal(body.realtimeConfig.skeleton_inference_node_config.execution_provider, 'cpu');
        return Response.json({resolved_config: body.realtimeConfig, camera_group_id: 'group', pipeline_id: 'pipeline'});
    });
    const result = await applyRealtimePipeline(requested)(store.dispatch, () => state, undefined);
    assert.equal(result.type, 'realtime/apply/fulfilled');
    assert.deepEqual(requests, [serverUrls.endpoints.realtimeConnectOrUpdate]);
});
