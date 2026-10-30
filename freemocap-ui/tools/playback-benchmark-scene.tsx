// Browser half of benchmark-playback.mjs; uses production decoding and renderers.
import React, {useEffect} from 'react';
import {createRoot} from 'react-dom/client';
import {Canvas, useFrame, useThree} from '@react-three/fiber';
import {decodePlaybackParquet} from '../src/services/recording/playback-parquet';
import {PlaybackManifestSchema, recordedKeypoints, recordedModelFrame} from '../src/services/recording/playback-data';
import {KeypointsSourceProvider} from '../src/components/viewport3d/KeypointsSourceContext';
import {ViewportStateProvider, useViewportState} from '../src/components/viewport3d/scene/ViewportStateContext';
import {KeypointsRenderer} from '../src/components/viewport3d/renderers/KeypointsRenderer';
import {ModelConnectionRenderer} from '../src/components/viewport3d/renderers/ModelConnectionRenderer';
import {RigidBodyBoneRenderer} from '../src/components/viewport3d/renderers/RigidBodyBoneRenderer';
import {getPickingEntries} from '../src/components/viewport3d/renderers/PickingRegistry';

const bench = window as any;
const wait = () => new Promise(resolve => setTimeout(resolve, 30));
const modelsListeners = new Set<any>();
const framesListeners = new Set<any>();
const pointsListeners = new Set<any>();
let currentModels: any[] = [];
let currentFrames: any[] = [];
let currentPoints: any = null;
let advanceScene: any;
let drawMilliseconds = 0;
let sceneState: any;
let latestStats: any;
const maximumStats: Record<string, number> = {};
const subscribe = (listeners: Set<any>, get: () => any) => (callback: any) => {
    listeners.add(callback); callback(get()); return () => {listeners.delete(callback);};
};
const source = {
    isLive: false, getModels: () => currentModels, getLatestModelFrames: () => currentFrames,
    getLatestKeypoints: () => currentPoints,
    subscribeToModels: subscribe(modelsListeners, () => currentModels),
    subscribeToModelFrames: subscribe(framesListeners, () => currentFrames),
    subscribeToKeypoints: subscribe(pointsListeners, () => currentPoints ?? {pointNames: [], interleaved: new Float32Array()}),
};
function ObserveScene() {
    const state = useThree();
    const {statsRef} = useViewportState();
    useEffect(() => {advanceScene = state.advance; sceneState = state;}, [state]);
    useFrame(({gl, scene, camera}) => {
        latestStats = {...statsRef.current};
        for (const [name, value] of Object.entries(latestStats)) maximumStats[name] = Math.max(maximumStats[name] ?? 0, value as number);
        const start = performance.now(); gl.render(scene, camera); drawMilliseconds = performance.now() - start;
    }, 1);
    return null;
}
createRoot(document.getElementById('root')!).render(<Canvas frameloop="never" camera={{position: [0, -3000, 1500], near: 1, far: 100000}}>
    <KeypointsSourceProvider source={source}><ViewportStateProvider>
        <KeypointsRenderer/><ModelConnectionRenderer/><RigidBodyBoneRenderer/><ObserveScene/>
    </ViewportStateProvider></KeypointsSourceProvider>
</Canvas>);

const median = (values: number[]) => [...values].sort((a, b) => a - b)[Math.floor(values.length / 2)];
const summarize = (values: number[]) => ({median_ms: median(values), samples_ms: values});
function heapBytes() {return (performance as any).memory?.usedJSHeapSize ?? null;}
async function digestChannels(channels: any[]) {
    const result = [];
    for (const channel of channels) {
        const bytes = new Uint8Array(channel.values.buffer, channel.values.byteOffset, channel.values.byteLength);
        const digest = await crypto.subtle.digest('SHA-256', bytes);
        result.push({channel: channel.channel, frames: channel.frame_numbers, times: channel.timestamps_s,
            values_sha256: [...new Uint8Array(digest)].map(value => value.toString(16).padStart(2, '0')).join(''),
            array_bytes: bytes.byteLength});
    }
    return result;
}
bench.runPlaybackBenchmark = async () => {
    while (!advanceScene) await wait();
    const manifest = PlaybackManifestSchema.parse(await (await fetch('/manifest.json')).json());
    const run = manifest.runs.find(item => item.run_id === manifest.selected_run_id)!;
    const group = run.channels[0].sensor_group;
    const times = run.timelines.find(item => item.sensor_group === group && item.source === `timing:${group}`)!.timestamps_s;
    const downloads: number[] = [], decodes: number[] = [], heapAfterDecode: number[] = [];
    let channels: any[] = [];
    for (let pass = 0; pass < 6; pass++) {
        const downloadStart = performance.now();
        const file = await (await fetch('/recording.parquet', {cache: 'no-store'})).arrayBuffer();
        const downloadTime = performance.now() - downloadStart;
        const decodeStart = performance.now();
        const runs = await decodePlaybackParquet(file, manifest);
        const decodeTime = performance.now() - decodeStart;
        channels = runs[run.run_id];
        if (pass) {downloads.push(downloadTime); decodes.push(decodeTime); heapAfterDecode.push(heapBytes());}
    }
    const values = await digestChannels(channels);
    currentModels = run.models;
    modelsListeners.forEach(callback => callback(currentModels));
    const prepare = (time: number) => {
        const frames = run.models.map(model => recordedModelFrame(run, {channels}, model, group, time));
        const points = recordedKeypoints(channels, group, time);
        return {frames, points: points ? {pointNames: points.names, interleaved: points.data} : {pointNames: [], interleaved: new Float32Array()}};
    };
    const dispatch = (frame: ReturnType<typeof prepare>) => {
        currentFrames = frame.frames; currentPoints = frame.points;
        framesListeners.forEach(callback => callback(currentFrames));
        pointsListeners.forEach(callback => callback(currentPoints));
    };
    dispatch(prepare(times[0]));
    await wait(); advanceScene(performance.now()); await wait();
    // Warm up complete renderer subscriptions and shaders before steady-state samples.
    for (const time of times) {dispatch(prepare(time)); advanceScene(performance.now());}
    const preparation: number[] = [], subscriptions: number[] = [], renderUpdates: number[] = [], submission: number[] = [];
    for (let pass = 0; pass < 5; pass++) {
        let prepareTime = 0, dispatchTime = 0, updateTime = 0, drawTime = 0;
        for (const time of times) {
            let start = performance.now(); const frame = prepare(time); prepareTime += performance.now() - start;
            start = performance.now(); dispatch(frame); dispatchTime += performance.now() - start;
            start = performance.now(); advanceScene(performance.now()); updateTime += performance.now() - start - drawMilliseconds;
            drawTime += drawMilliseconds;
        }
        preparation.push(prepareTime / times.length); subscriptions.push(dispatchTime / times.length);
        renderUpdates.push(updateTime / times.length); submission.push(drawTime / times.length);
    }
    const gl = sceneState.gl.getContext();
    const rendererInfo = gl.getExtension('WEBGL_debug_renderer_info');
    // Save untouched production geometry for toleranced before/after comparisons.
    // Inspection is outside measured loops; null in JSON represents a non-finite float.
    const geometryEvidence = [];
    for (const frameIndex of [0, Math.floor(times.length / 2), times.length - 1]) {
        dispatch(prepare(times[frameIndex])); advanceScene(performance.now());
        const meshes: any[] = [];
        sceneState.scene.traverse((object: any) => {
            if (object.isInstancedMesh) meshes.push({kind: getPickingEntries().get(object)?.kind ?? 'instanced-mesh', name: object.name,
                instance_names: [...(getPickingEntries().get(object)?.instanceIdToName ?? [])],
                geometry: object.geometry.type, count: object.count,
                instance_matrix: Array.from(object.instanceMatrix.array),
                instance_color: object.instanceColor ? Array.from(object.instanceColor.array) : null});
            else if (object.isLineSegments2) meshes.push({kind: 'model-connections', name: object.name,
                positions: Array.from(object.geometry.attributes.instanceStart.data.array),
                colors: Array.from(object.geometry.attributes.instanceColorStart.data.array)});
        });
        geometryEvidence.push({frame_index: frameIndex, timestamp_s: times[frameIndex], meshes});
    }
    return {frame_count: times.length, run_id: run.run_id, sensor_group: group,
        download: summarize(downloads), decode: summarize(decodes), frame_preparation: summarize(preparation),
        renderer_subscriptions: summarize(subscriptions), renderer_cpu_update: summarize(renderUpdates),
        webgl_command_submission: summarize(submission), heap_after_decode_bytes: heapAfterDecode,
        final_js_heap_bytes: heapBytes(), retained_channel_value_bytes: values.reduce((sum, item) => sum + item.array_bytes, 0),
        final_renderer_stats: latestStats, maximum_renderer_stats: maximumStats, channel_fingerprints: values,
        geometry_evidence: geometryEvidence,
        webgl_renderer: rendererInfo ? gl.getParameter(rendererInfo.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER)};
};
