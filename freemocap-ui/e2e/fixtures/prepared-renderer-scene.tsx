import React, {useEffect} from 'react';
import {createRoot} from 'react-dom/client';
import {Canvas, useThree} from '@react-three/fiber';
import {Raycaster, Vector3} from 'three';
import {KeypointsSourceProvider, type KeypointsFrame, type KeypointsCallback, type KeypointsSource} from '../../src/components/viewport3d/KeypointsSourceContext';
import {workerDataStore} from '../../src/components/viewport3d/WorkerDataStore';
import {ViewportStateProvider, useViewportState} from '../../src/components/viewport3d/scene/ViewportStateContext';
import {KeypointsRenderer} from '../../src/components/viewport3d/renderers/KeypointsRenderer';
import {RigidBodyBoneRenderer} from '../../src/components/viewport3d/renderers/RigidBodyBoneRenderer';
import {ModelConnectionRenderer} from '../../src/components/viewport3d/renderers/ModelConnectionRenderer';
import {FaceRenderer} from '../../src/components/viewport3d/renderers/FaceRenderer';
import {SegmentAxesRenderer} from '../../src/components/viewport3d/renderers/SegmentAxesRenderer';
import {getPickingEntries} from '../../src/components/viewport3d/renderers/PickingRegistry';

import {ViewportPicker} from '../../src/components/viewport3d/renderers/ViewportPicker';
import {computeInspectionDetails} from '../../src/components/viewport3d/scene/inspection-details';

let directPoints: KeypointsFrame | null = null;
const directSubscribers = new Set<KeypointsCallback>();
const source: KeypointsSource & Pick<typeof workerDataStore, 'dispatch'> = {
    ...workerDataStore,
    get isLive() {return workerDataStore.isLive;},
    getLatestKeypoints: () => directPoints ?? workerDataStore.getLatestKeypoints(),
    subscribeToKeypoints: callback => {
        directSubscribers.add(callback);
        const unsubscribe = workerDataStore.subscribeToKeypoints(callback);
        return () => {directSubscribers.delete(callback); unsubscribe();};
    },
};

const api = window as any;
let state: any;
function Observe() {const current = useThree(); const inspection = useViewportState(); useEffect(() => {state = current; api.inspectionState = {hovered: inspection.hovered, pinned: inspection.pinned};}, [current, inspection.hovered, inspection.pinned]); return null;}
createRoot(document.getElementById('root')!).render(<Canvas frameloop="never">
    <KeypointsSourceProvider source={source}><ViewportStateProvider>
        <KeypointsRenderer/><RigidBodyBoneRenderer/><ModelConnectionRenderer/><FaceRenderer/><SegmentAxesRenderer/><ViewportPicker/><Observe/>
    </ViewportStateProvider></KeypointsSourceProvider>
</Canvas>);
const wait = () => new Promise(resolve => setTimeout(resolve, 20));
api.renderFixture = async (input: any) => {
    while (!state) await wait();
    if (input.live !== undefined) source.dispatch('livePresentation', input.live);
    if (input.definitions) source.dispatch('models', input.definitions);
    if (input.frames) source.dispatch('modelFrames', input.frames.map((frame: any) => ({...frame,
        ...Object.fromEntries(['segmentOrigins', 'landmarks', 'mappedKeypoints', 'segmentLengths'].map(field => [field,
            frame[field] ? {...frame[field], data: Float32Array.from(frame[field].data, value => value === null ? NaN : value as number)} : null])),
        rotations: frame.rotations ? {...frame.rotations, worldQuaternions: Float32Array.from(frame.rotations.worldQuaternions ?? []), localQuaternions: Float32Array.from(frame.rotations.localQuaternions ?? [])} : null,
    })));
    if (input.points?.pointSources) {
        directPoints = {pointNames: input.points.pointNames, pointSources: input.points.pointSources.map((entry: any) =>
            ({...entry, data: Float32Array.from(entry.data, value => value === null ? NaN : value as number)}))};
        directSubscribers.forEach(callback => callback(directPoints!));
    } else if (input.points) {
        directPoints = null;
        source.dispatch('keypoints', {...input.points, interleaved: Float32Array.from(input.points.interleaved, value => value === null ? NaN : value as number)});
    }
    await wait();
    state.advance(performance.now());
    const result: any = {meshes: [], lines: [], dots: []};
    state.scene.traverse((object: any) => {
        if (object.isInstancedMesh) {
            const entry = getPickingEntries().get(object);
            result.meshes.push({kind: entry?.kind, uuid: object.uuid, names: [...entry?.instanceTargets ?? []].map(([slot, target]) => [slot, target.name]), targets: [...entry?.instanceTargets ?? []],
                matrices: Array.from(object.instanceMatrix.array), colors: Array.from(object.instanceColor.array),
                capacity: object.instanceMatrix.count, count: object.count, matrixVersion: object.instanceMatrix.version, colorVersion: object.instanceColor.version});
        } else if (object.isLineSegments2) result.connections = {positions: Array.from(object.geometry.attributes.instanceStart.data.array), colors: Array.from(object.geometry.attributes.instanceColorStart.data.array)};
        else if (object.isPoints) result.dots = Array.from(object.geometry.attributes.position.array).slice(0, object.geometry.drawRange.count * 3);
        else if (object.isLineSegments) result.lines.push(Array.from(object.geometry.attributes.position?.array ?? []).slice(0, object.geometry.drawRange.count * 3));
    });
    return result;
};
api.pickFixture = (kind: string, slot: number) => {
    for (const [mesh, entry] of getPickingEntries()) if (entry.kind === kind) {
        const matrix = mesh.instanceMatrix.array, i = slot * 16;
        mesh.updateMatrixWorld(true); mesh.computeBoundingSphere();
        const ray = new Raycaster(new Vector3(matrix[i + 12], matrix[i + 13], matrix[i + 14] + 1000), new Vector3(0, 0, -1));
        return ray.intersectObject(mesh).map(hit => ({slot: hit.instanceId, name: entry.instanceTargets.get(hit.instanceId!)?.name}));
    }
    return [];
};

api.inspectFixture = (target: any) => computeInspectionDetails(structuredClone(target), source, source.getLatestModelFrames(), new Map((source.getModels() ?? []).map(model => [model.model_id, model])));
api.pointFixture = async (kind: string, slot: number, pin = false) => {
    for (const [mesh, entry] of getPickingEntries()) if (entry.kind === kind) {
        state.camera.position.set(1000, 0, 5000); state.camera.far = 20000;
        state.camera.lookAt(1000, 0, 0); state.camera.updateProjectionMatrix(); state.camera.updateMatrixWorld();
        const matrix = mesh.instanceMatrix.array, index = slot * 16;
        const position = new Vector3(matrix[index + 12], matrix[index + 13], matrix[index + 14]).applyMatrix4(mesh.matrixWorld).project(state.camera);
        const clientX = (position.x + 1) * state.size.width / 2, clientY = (1 - position.y) * state.size.height / 2;
        const canvas = state.gl.domElement;
        canvas.dispatchEvent(new PointerEvent('pointermove', {clientX, clientY}));
        if (pin) {canvas.dispatchEvent(new PointerEvent('pointerdown', {clientX, clientY})); canvas.dispatchEvent(new PointerEvent('pointerup', {clientX, clientY}));}
        await wait(); return api.inspectionState;
    }
};
