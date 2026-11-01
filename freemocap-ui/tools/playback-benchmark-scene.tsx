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
import {FaceRenderer} from '../src/components/viewport3d/renderers/FaceRenderer';
import {RigidBodyBoneRenderer} from '../src/components/viewport3d/renderers/RigidBodyBoneRenderer';
import {getPickingEntries} from '../src/components/viewport3d/renderers/PickingRegistry';
import {prepareFrameLayout, writeFrameBuffer, readFrameBuffer} from '../src/components/viewport3d/viewport-frame-codec';
import {ViewportFrameSender} from '../src/components/viewport3d/viewport-frame-transfer';

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
let setVisibility: any;
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
    const {statsRef, setVisibility: changeVisibility} = useViewportState();
    setVisibility = changeVisibility;
    useEffect(() => {advanceScene = state.advance; sceneState = state;}, [state]);
    useFrame(({gl, scene, camera}) => {
        latestStats = {...statsRef.current};
        for (const [name, value] of Object.entries(latestStats)) maximumStats[name] = Math.max(maximumStats[name] ?? 0, value as number);
        const start = performance.now(); gl.render(scene, camera); drawMilliseconds = performance.now() - start;
    }, 1);
    return null;
}
function BenchmarkLayers() {
    const {visibility} = useViewportState();
    return <><KeypointsRenderer/>{visibility.boneLines && <ModelConnectionRenderer/>}
        {visibility.bones && <RigidBodyBoneRenderer/>}
        {(visibility.face || visibility.faceConnections) && <FaceRenderer/>}<ObserveScene/></>;
}
createRoot(document.getElementById('root')!).render(<Canvas frameloop="never" camera={{position: [0, -3000, 1500], near: 1, far: 100000}}>
    <KeypointsSourceProvider source={source}><ViewportStateProvider>
        <BenchmarkLayers/>
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
    // Exercise all point layers even when the app starts with observations hidden.
    setVisibility((value: any) => ({...value, rawKeypoints: true, mappedKeypoints: true, landmarks: true, faceConnections: true}));
    await wait();
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
    const updateFrames: number[] = [], submissionFrames: number[] = [];
    for (let pass = 0; pass < 5; pass++) {
        let prepareTime = 0, dispatchTime = 0, updateTime = 0, drawTime = 0;
        for (const time of times) {
            let start = performance.now(); const frame = prepare(time); prepareTime += performance.now() - start;
            start = performance.now(); dispatch(frame); dispatchTime += performance.now() - start;
            start = performance.now(); advanceScene(performance.now()); const update = performance.now() - start - drawMilliseconds; updateTime += update;
            updateFrames.push(update); submissionFrames.push(drawMilliseconds);
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
                instance_targets: [...(getPickingEntries().get(object)?.instanceTargets ?? [])],
                geometry: object.geometry.type, count: object.count,
                instance_matrix: Array.from(object.instanceMatrix.array),
                instance_color: object.instanceColor ? Array.from(object.instanceColor.array) : null});
            else if (object.isLineSegments2) meshes.push({kind: 'model-connections', name: object.name,
                positions: Array.from(object.geometry.attributes.instanceStart.data.array),
                colors: Array.from(object.geometry.attributes.instanceColorStart.data.array)});
        });
        geometryEvidence.push({frame_index: frameIndex, timestamp_s: times[frameIndex], meshes});
    }
    // Validate live/playback's shared numeric boundary against actual production geometry.
    // This inspection is deliberately outside timing samples.
    const capture = () => {
        const arrays: number[][] = [];
        sceneState.scene.traverse((object: any) => {
            if (object.isInstancedMesh) arrays.push(Array.from(object.instanceMatrix.array));
            if (object.isLineSegments2) {
                if (object.frustumCulled) throw new Error('Dynamic line batch must not use stale local bounds');
                arrays.push(Array.from(object.geometry.attributes.instanceStart.data.array));
            }
            if (object.userData.attachedSurface) arrays.push([+object.visible, ...object.matrix.elements,
                ...object.geometry.attributes.position.array, ...object.geometry.index.array, object.material.opacity]);
            if (object.isPoints || (object.isLineSegments && !object.isLineSegments2)) arrays.push([
                +object.visible, object.geometry.drawRange.count,
                ...object.geometry.attributes.position.array.slice(0, object.geometry.drawRange.count * 3)]);
        });
        // Mount order is not semantic; remounting one layer may move it past another.
        return JSON.stringify(arrays.map(value => JSON.stringify(value)).sort());
    };
    const selected = prepare(times[Math.floor(times.length / 2)]);
    dispatch(selected); advanceScene(performance.now());
    const directGeometry = capture();
    const transferLayout = prepareFrameLayout('modelFrames', selected.frames);
    const transfer = new ArrayBuffer(transferLayout.byteLength);
    writeFrameBuffer(transfer, transferLayout, 'modelFrames', selected.frames);
    dispatch({...selected, frames: readFrameBuffer(transfer, transferLayout, 'modelFrames') as typeof selected.frames});
    advanceScene(performance.now());
    if (capture() !== directGeometry) throw new Error('Transferred and direct playback renderer geometry differ');
    const picking = () => JSON.stringify([...getPickingEntries().values()].map(entry => JSON.stringify([...entry.instanceTargets])).sort());
    const originalPicking = picking();
    // Equal-size replacement must invalidate prepared data and keep semantic picking identities.
    currentModels = structuredClone(run.models);
    modelsListeners.forEach(callback => callback(currentModels));
    dispatch(selected); advanceScene(performance.now());
    if (capture() !== directGeometry || picking() !== originalPicking) throw new Error('Model replacement changed geometry or picking');
    const attachedEdges = run.models.reduce((sum, model) => sum + (model.presentation?.attached_lines.reduce((n, item) => n + item.positions.length / 6, 0) ?? 0), 0);
    if (attachedEdges) {
        const missing = selected.frames.map(frame => {
            const quats = frame.rotations?.worldQuaternions.slice();
            for (const lines of run.models.find(model => model.model_id === frame.modelId)?.presentation?.attached_lines ?? []) {
                const row = frame.rotations?.boneNames.indexOf(lines.segment) ?? -1;
                if (quats && row >= 0) quats.fill(NaN, row * 4, row * 4 + 4);
            }
            return {...frame, rotations: frame.rotations && {...frame.rotations, worldQuaternions: quats!}};
        });
        dispatch({...selected, frames: missing}); advanceScene(performance.now());
        sceneState.scene.traverse((object: any) => {
            if (object.isLineSegments2 && !Array.from(object.geometry.attributes.instanceStart.data.array as Float32Array)
                .slice(-attachedEdges * 6).every(value => value === 1e5)) throw new Error('Missing pose left a visible contour');
            if (object.userData.attachedSurface && object.visible) throw new Error('Missing pose left a visible surface');
        });
        dispatch(selected); advanceScene(performance.now());
        if (capture() !== directGeometry) throw new Error('Missing-pose recovery changed geometry');
    }
    setVisibility((value: any) => ({...value, boneLines: false, bones: false}));
    await wait(); advanceScene(performance.now());
    let hiddenLineObjects = 0;
    sceneState.scene.traverse((object: any) => {if (object.isLineSegments2 || object.userData.attachedSurface) hiddenLineObjects++;});
    if (hiddenLineObjects || [...getPickingEntries().values()].some(entry => entry.kind === 'segment')) {
        throw new Error('Hidden renderers retained objects or picking registrations');
    }
    setVisibility((value: any) => ({...value, boneLines: true, bones: true}));
    await wait(); dispatch(selected); advanceScene(performance.now());
    if (capture() !== directGeometry || picking() !== originalPicking) throw new Error('Visibility remount changed geometry or picking');
    const parity = {equal: true, model_switch_and_picking: true, visibility_remount: true, missing_pose_recovery: true,
        frame_bytes: transfer.byteLength, attached_edges: attachedEdges};
    const percentiles = (values: number[]) => {const sorted = [...values].sort((a, b) => a - b); return {p50_ms: sorted[Math.floor(sorted.length * .5)], p95_ms: sorted[Math.floor(sorted.length * .95)]};};
    // Five paired display comparisons on identical recorded values. Only the test
    // baseline removes this feature's declarations; production never infers styles.
    const legacyModels = run.models.map(model => ({...model, presentation: undefined, tracker_connections: undefined,
        landmark_connections: model.landmark_connections.filter(group => !['thorax_bridge', 'pelvis_rim_and_struts'].includes(group.name))}));
    const paired: any[] = [];
    for (let pair = 0; pair < 5; pair++) {
        const measurements: any = {};
        for (const mode of (pair % 2 ? ['selected', 'baseline'] : ['baseline', 'selected'])) {
            currentModels = mode === 'selected' ? run.models : legacyModels;
            modelsListeners.forEach(callback => callback(currentModels));
            dispatch(selected); advanceScene(performance.now());
            const cpu: number[] = [], draw: number[] = [];
            let maxDrawCalls = 0;
            for (const time of times) {
                dispatch(prepare(time));
                const start = performance.now(); advanceScene(performance.now());
                cpu.push(performance.now() - start - drawMilliseconds); draw.push(drawMilliseconds);
                maxDrawCalls = Math.max(maxDrawCalls, sceneState.gl.info.render.calls);
            }
            measurements[mode] = {update: percentiles(cpu), submission: percentiles(draw),
                mean_update_ms: cpu.reduce((a, b) => a + b, 0) / cpu.length, draw_calls: maxDrawCalls};
        }
        paired.push(measurements);
    }
    currentModels = run.models; modelsListeners.forEach(callback => callback(currentModels));
    dispatch(selected); advanceScene(performance.now());
    const resourceSamples: any[] = [];
    for (let cycle = 0; cycle < 20; cycle++) {
        currentModels = structuredClone(run.models); modelsListeners.forEach(callback => callback(currentModels));
        dispatch(selected); advanceScene(performance.now());
        setVisibility((value: any) => ({...value, boneLines: false, bones: false}));
        await wait(); advanceScene(performance.now());
        const hiddenGeometries = sceneState.gl.info.memory.geometries;
        setVisibility((value: any) => ({...value, boneLines: true, bones: true}));
        await wait(); dispatch(selected); advanceScene(performance.now());
        resourceSamples.push({cycle, hidden_geometries: hiddenGeometries, visible_geometries: sceneState.gl.info.memory.geometries,
            programs: sceneState.gl.info.programs.length, picking_meshes: getPickingEntries().size});
    }
    if (resourceSamples.some(sample => sample.visible_geometries !== resourceSamples[0].visible_geometries
        || sample.programs !== resourceSamples[0].programs || sample.picking_meshes !== resourceSamples[0].picking_meshes)) {
        throw new Error('Renderer resources grew during model replacement/visibility cycles');
    }
    if (capture() !== directGeometry || picking() !== originalPicking) throw new Error('Lifecycle workload changed geometry/picking');
    const faceResources: number[] = [];
    for (let cycle = 0; cycle < 20; cycle++) {
        for (const [points, connections] of [[true, false], [false, true], [false, false], [true, true]]) {
            setVisibility((value: any) => ({...value, face: points, faceConnections: connections}));
            await wait(); dispatch(selected); advanceScene(performance.now());
            const objects: any[] = [];
            sceneState.scene.traverse((object: any) => {
                if (object.isPoints || (object.isLineSegments && !object.isLineSegments2)) objects.push(object);
            });
            if (objects.length !== (points || connections ? 2 : 0)) throw new Error('Face toggle retained or lost render objects');
            for (const object of objects) {
                if (object.visible !== ((object.isPoints ? points : connections) && object.geometry.drawRange.count > 0)) throw new Error('Face toggles are not independent');
            }
            if (points && connections) faceResources.push(sceneState.gl.info.memory.geometries);
        }
    }
    if (new Set(faceResources).size !== 1 || capture() !== directGeometry) throw new Error('Face remount leaks or changes visible geometry');
    Object.assign(parity, {independent_face_toggles: true, face_lifecycle_cycles: 20, face_visible_geometries: faceResources[0]});
    const workerSamples: any[] = [];
    for (let pair = 0; pair < 5; pair++) {
        const measurements: any = {};
        for (const mode of (pair % 2 ? ['selected', 'baseline'] : ['baseline', 'selected'])) {
            const worker = new Worker('/transfer-worker.js', {type: 'module'});
            let sequence = 0, returned = 0, packets = 0, bytes = 0, maxAllocated = 0;
            const pending = new Map<number, () => void>();
            const sender = new ViewportFrameSender((message: any, transfers) => {
                if (message.type === 'viewportFrame') {packets++; bytes = message.buffer.byteLength;}
                worker.postMessage(message, transfers ?? []);
            });
            worker.onmessage = event => {
                sender.receive(event.data);
                if (event.data.type === 'viewportBufferReturned') returned++;
                if (event.data.type === 'probe') {pending.get(event.data.id)?.(); pending.delete(event.data.id);}
            };
            const probe = () => new Promise<void>(resolve => {
                const id = ++sequence; pending.set(id, resolve); worker.postMessage({type: 'probe', id});
            });
            const latency: number[] = [];
            try {
                worker.postMessage({type: 'models', data: mode === 'selected' ? run.models : legacyModels});
                await probe();
                for (const time of times) {
                    const frame = prepare(time);
                    const start = performance.now(); sender.sendModels(frame.frames); await probe();
                    latency.push(performance.now() - start);
                    maxAllocated = Math.max(maxAllocated, (sender as any).streams.get('modelFrames').allocated);
                }
                sender.dispose(); await probe();
                if (returned !== packets || maxAllocated > run.models.length + 2) throw new Error('Unbounded or unreleased worker buffers');
                measurements[mode] = {round_trip: percentiles(latency), packets, returned, max_allocated: maxAllocated,
                    frame_bytes: bytes, over_33ms: latency.filter(value => value > 1000 / 30).length};
            } finally {sender.dispose(); worker.terminate();}
        }
        workerSamples.push(measurements);
    }
    return {frame_count: times.length, run_id: run.run_id, sensor_group: group,
        renderer_frame_distribution: percentiles(updateFrames), submission_frame_distribution: percentiles(submissionFrames),
        transferred_geometry_parity: parity,
        paired_display_comparison: paired, resource_lifecycle: resourceSamples,
        paired_worker_transfer: workerSamples,
        render_calls: sceneState.gl.info.render.calls, gpu_geometries: sceneState.gl.info.memory.geometries,
        download: summarize(downloads), decode: summarize(decodes), frame_preparation: summarize(preparation),
        renderer_subscriptions: summarize(subscriptions), renderer_cpu_update: summarize(renderUpdates),
        webgl_command_submission: summarize(submission), heap_after_decode_bytes: heapAfterDecode,
        final_js_heap_bytes: heapBytes(), retained_channel_value_bytes: values.reduce((sum, item) => sum + item.array_bytes, 0),
        final_renderer_stats: latestStats, maximum_renderer_stats: maximumStats, channel_fingerprints: values,
        geometry_evidence: geometryEvidence,
        webgl_renderer: rendererInfo ? gl.getParameter(rendererInfo.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER)};
};
