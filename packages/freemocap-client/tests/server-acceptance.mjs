/** Explicit integration run; requires an owned server and private reference copies. */
import assert from 'node:assert/strict';
import {readFile, writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {setTimeout as delay} from 'node:timers/promises';
import {createClient, ApiError} from '../dist/index.js';
import {PlaybackManifestSchema, decodeRecordingParquet} from '../dist/recording/index.js';

const inventory = JSON.parse(await readFile(new URL('../contracts/operations.json', import.meta.url), 'utf8'));
const config = JSON.parse(await readFile(process.argv[2], 'utf8'));
const client = createClient({baseUrl: config.url});
const operations = client.operations;
const report = {recordings: [], messageKinds: [], failures: [], exports: []};
const messages = [], protocolErrors = [];
client.stream.subscribeToMessages(message => messages.push(message));
client.stream.subscribeToProtocolErrors(error => protocolErrors.push(String(error)));
async function until(predicate, description, timeout = 30000) {
    const deadline = Date.now() + timeout;
    while (!predicate()) {
        if (Date.now() > deadline) throw new Error(`Timed out: ${description}`);
        await delay(50);
    }
}
async function fails(status, action) {
    await assert.rejects(action, error => error instanceof ApiError && error.status === status);
    report.failures.push(status);
}
try {
    assert.equal((await operations.healthcheck_endpoint_health_get()).data.pid, config.pid);
    const schema = (await client.schema()).data;
    assert.equal(Object.values(schema.paths).reduce((count, path) => count + Object.values(path).filter(item => item.operationId).length, 0), inventory.public_http.length);
    client.stream.connect();
    await until(() => messages.some(item => item.kind === 'app_state') && messages.some(item => item.kind === 'progress'), 'initial independent snapshots');
    const tasks = (await operations.all_tasks_freemocap_tasks_get()).data;
    assert.equal(messages.find(item => item.kind === 'progress').snapshot.server_instance_id, tasks.server_instance_id);
    await operations.temporal_config_status_freemocap_realtime_filter_config_get();
    await operations.running_pipeline_config_freemocap_realtime_config_get();
    await operations.get_session_providers_freemocap_onnx_session_providers_get();
    await fails(404, () => operations.get_task_freemocap_tasks__task_id__get({path: {task_id: 'export:missing-sdk-task'}}));
    await fails(422, () => operations.capture_start_calibration_recording({body: {invalid: true}}));
    const aborted = new AbortController(); aborted.abort();
    await assert.rejects(() => operations.healthcheck_endpoint_health_get({signal: aborted.signal}), {name: 'AbortError'});
    report.abort = 'AbortError without a server mutation';

    for (const reference of config.recordings) {
        const input = {path: {recording_id: reference.id}, query: {recording_parent_directory: reference.parent}};
        const manifest = PlaybackManifestSchema.parse((await operations.recordings_get_playback_manifest(input)).data);
        const expected = JSON.parse(await readFile(reference.expected, 'utf8'));
        assert.equal(manifest.selected_run_id, expected.run_id);
        const range = await operations.recordings_get_recording_parquet({...input, headers: {Range: 'bytes=0-31'}});
        assert.equal(range.status, 206); assert.equal((await range.data.arrayBuffer()).byteLength, 32);
        const download = await operations.recordings_get_recording_parquet(input);
        const buffer = await download.data.arrayBuffer();
        assert.equal(createHash('sha256').update(new Uint8Array(buffer)).digest('hex'), reference.sha256);
        const decoded = await decodeRecordingParquet(buffer, manifest);
        const actual = decoded[expected.run_id].find(item => ['sensor_group', 'source', 'reference_frame', 'kind'].every(key => item.channel[key] === expected.channel[key]));
        assert.ok(actual, 'declared reference channel exists');
        assert.deepEqual(actual.channel, expected.channel);
        assert.deepEqual(actual.frame_numbers, expected.frames);
        assert.deepEqual(actual.timestamps_s, expected.times);
        assert.equal(actual.values.length, expected.values.length);
        expected.values.forEach((value, index) => value === null ? assert.ok(Number.isNaN(actual.values[index])) : assert.equal(actual.values[index], value));
        await operations.list_recording_runs_freemocap_recordings__recording_id__runs_get(input);
        await operations.list_run_channels_freemocap_recordings__recording_id__runs__run_id__channels_get({...input, path: {...input.path, run_id: expected.run_id}});
        await fails(404, () => operations.list_run_channels_freemocap_recordings__recording_id__runs__run_id__channels_get({...input, path: {...input.path, run_id: 999999}}));
        await fails(409, () => operations.create_export_freemocap_recordings__recording_id__exports_post({...input, body: {kind: 'channels', data: ['LANDMARKS_3D'], formats: ['npz'], expected_revision: 'stale-sdk-revision'}}));
        report.recordings.push({id: reference.id, frames: actual.frame_numbers.length, comparedValues: actual.values.length, decodedChannels: decoded[expected.run_id].length, revision: manifest.revision});
        if (report.recordings.length === 1) {
            const accepted = await operations.create_export_freemocap_recordings__recording_id__exports_post({...input, body: {kind: 'channels', data: ['LANDMARKS_3D'], formats: ['npz'], expected_revision: manifest.revision, run_id: expected.run_id}});
            assert.equal(accepted.status, 202);
            let task;
            const deadline = Date.now() + 90000;
            do {
                task = (await operations.get_task_freemocap_tasks__task_id__get({path: {task_id: accepted.data.task_id}})).data;
                if (['complete', 'failed', 'cancelled'].includes(task.status)) break;
                assert.ok(Date.now() < deadline, 'export finishes within deadline'); await delay(100);
            } while (true);
            assert.equal(task.status, 'complete', JSON.stringify(task));
            const inventory = (await operations.list_exports_freemocap_recordings__recording_id__exports_get({...input, query: {...input.query, verify: true}})).data;
            assert.ok(inventory.artifacts.length > 0);
            assert.ok(inventory.artifacts.every(item => item.exists && item.integrity === 'valid' && item.stale === false));
            await until(() => messages.some(item => item.kind === 'progress' && item.snapshot.tasks.some(entry => entry.task_id === task.task_id && entry.status === 'complete')), 'terminal export snapshot over WebSocket');
            report.exports.push({task_id: task.task_id, status: task.status, artifacts: inventory.artifacts});
        }
    }
    const first = config.recordings[0];
    await fails(404, () => operations.recordings_get_playback_manifest({path: {recording_id: 'missing-sdk-recording'}, query: {recording_parent_directory: first.parent}}));
    const before = messages.length;
    client.stream.disconnect(); client.stream.connect();
    await until(() => messages.slice(before).some(item => item.kind === 'app_state') && messages.slice(before).some(item => item.kind === 'progress'), 'snapshots after reconnect');
    assert.deepEqual(protocolErrors, []);
    report.messageKinds = [...new Set(messages.map(item => item.kind))];
    report.reconnect = 'new independent snapshots received';
    await writeFile(config.report, JSON.stringify(report, null, 2) + '\n');
    console.log(JSON.stringify(report));
} finally { client.close(); }
