/** Run only during an explicitly assigned physical camera/GPU slot. */
import assert from 'node:assert/strict';
import {readFile, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {setTimeout as delay} from 'node:timers/promises';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {createClient} from '../dist/index.js';
const config = JSON.parse(await readFile(process.argv[2], 'utf8'));
const client = createClient({baseUrl: config.url}), api = client.operations;
const report = {status: 'running', protocolErrors: []};
let latest, state, recording = false, samples = [], resolved = 0;
client.stream.subscribeToProtocolErrors(error => report.protocolErrors.push(String(error)));
client.stream.subscribeToAppState(message => {state = message.state;});
client.stream.subscribeToModelFrames(models => {if (models.length) resolved++;});
client.stream.subscribeToMessages(message => {
    if (message.kind === 'frame') {
        latest = message;
        samples.push({frameNumber: message.frame_number, timestamp: message.timestamp, arrivalMs: performance.now()});
    }
});
async function until(predicate, label, milliseconds = 180000) {
    const deadline = Date.now() + milliseconds;
    while (!predicate()) {assert.ok(Date.now() < deadline, `Timed out: ${label}`); await delay(50);}
}
try {
    assert.equal((await api.healthcheck_endpoint_health_get()).data.pid, config.pid);
    client.stream.connect();
    await api.camera_group_apply_post_endpoint_skellycam_camera_group_apply_post({body: {camera_configs: config.cameraConfigs, backend: 'python'}, signal: AbortSignal.timeout(60000)});
    await api.pipeline_apply_endpoint_freemocap_realtime_apply_post({body: {cameraConfigs: null, realtimeCameraIds: null, realtimeConfig: config.pipelineConfig}, signal: AbortSignal.timeout(180000)});
    await until(() => latest?.trackers.length && latest?.instances.length && resolved > 0 && state, 'tracked, resolved frame and app state');
    client.stream.sendDisplayFeedback(latest.frame_number, config.imageSizes);
    await delay(5000);
    report.providers = (await api.get_session_providers_freemocap_onnx_session_providers_get()).data;
    const models = report.providers.flatMap(pipeline => pipeline.models);
    assert.ok(models.length > 0 && models.every(model => model.applied_providers.includes('CUDAExecutionProvider')), JSON.stringify(report.providers));
    const observed = Object.assign({}, ...Object.values(state.camera_groups).map(group => group.configs));
    assert.deepEqual(Object.keys(observed).sort(), Object.keys(config.cameraConfigs).sort());
    await writeFile(path.join(config.output, 'observed-camera-configs.json'), JSON.stringify(observed, null, 2));
    samples = []; resolved = 0;
    await api.start_recording_skellycam_camera_group_all_record_start_post({body: {recording_name: 'sdk-capture', recording_directory: config.recordingDirectory, mic_device_index: -1}});
    recording = true;
    await delay(5000);
    report.recordings = (await api.stop_recording_skellycam_camera_group_all_record_stop_post()).data;
    recording = false;
    assert.ok(samples.length >= 3 && resolved > 0);
    assert.ok(samples.every((sample, index) => index === 0 || sample.frameNumber > samples[index - 1].frameNumber));
    report.samples = samples;
    report.resolvedFrames = resolved;
    report.models = latest.models.map(model => model.model_id);
    report.cameras = latest.cameras.map(camera => camera.id);
    assert.deepEqual([...report.cameras].sort(), Object.keys(config.cameraConfigs).sort());
    assert.equal(report.protocolErrors.length, 0);
    assert.ok(latest.image?.byteLength);
    await writeFile(path.join(config.output, 'image.bin'), latest.image);
    for (const recording of report.recordings) {
        const folder = recording.recording_path;
        const input = {path: {recording_id: path.basename(folder)}, query: {recording_parent_directory: path.dirname(folder)}};
        const videos = (await api.recordings_list_videos(input)).data.sources.synchronized.videos;
        assert.equal(videos.length, Object.keys(config.cameraConfigs).length);
        const response = await client.assetResponse(videos[0].stream_url, {headers: {Range: 'bytes=0-31'}});
        assert.equal(response.status, 206); assert.equal((await response.arrayBuffer()).byteLength, 32);
    }
    // One streaming consumer: retire the headless session before observing the app.
    client.close();
    const ui = await promisify(execFile)('node', ['tools/hardware-ui.mjs', '--server', config.url,
        '--output', path.join(config.output, 'ui'), '--seconds', '20', '--expected-configs', path.join(config.output, 'observed-camera-configs.json')],
        {cwd: config.uiRoot, windowsHide: true, timeout: 180000, maxBuffer: 8 * 1024 * 1024});
    await writeFile(path.join(config.output, 'ui-console.log'), ui.stdout + ui.stderr);
    report.productionUi = '20-second observation passed';
    report.status = 'passed';
} catch (error) {report.error = String(error.stack); throw error;}
finally {
    client.close();
    if (recording) await api.stop_recording_skellycam_camera_group_all_record_stop_post().catch(error => {report.stopError = String(error);});
    await api.stop_realtime_pipelines().catch(error => {report.pipelineStopError = String(error);});
    await api.close_all_camera_groups_skellycam_camera_group_close_all_delete().catch(error => {report.cameraCloseError = String(error);});
    await writeFile(path.join(config.output, 'sdk-live-report.json'), JSON.stringify(report, null, 2));
}
