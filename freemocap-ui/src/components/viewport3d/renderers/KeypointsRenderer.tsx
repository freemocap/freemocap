import { useEffect, useMemo, useRef } from "react";
import { Color, InstancedMesh, MeshBasicMaterial, SphereGeometry } from "three";
import { useFrame, useThree } from "@react-three/fiber";
import { useViewportState } from "../scene/ViewportStateContext";
import { LAYER_HEX } from "../helpers/layer-colors";
import { classifyPointName, getPointStyle } from "../helpers/skeleton-config";
import { registerPickingMesh, unregisterPickingMesh } from "./PickingRegistry";
import { useKeypointsSource, useModelDefinitionsById, type KeypointsFrame } from "../KeypointsSourceContext";
import type { ResolvedModelFrame } from "@/services/server/transport/frame-types";
import { finitePoint, hideMatrix, sameNames, prepareModels, preparedModelsMatch, XYZ_OFFSETS, type PreparedModel } from "./prepared-models";
import { ensureInstanceBuffers } from "./instance-buffers";

import type {InspectionTarget} from "../helpers/viewport3d-types";

const MAX_POINTS = 1024; // Initial capacity; grows for larger declared layouts.
const MAPPED_KEYPOINT_RADIUS = 0.12;
const RAW_KEYPOINT_COLOR = new Color(LAYER_HEX.rawKeypoints);
const MAPPED_KEYPOINT_COLOR = new Color(LAYER_HEX.mappedKeypoints);
function getKeypointRadius(name: string): number {
    switch (classifyPointName(name)) {
        case "face": return 0.075;
        case "left_hand": case "right_hand": return 0.1125;
        case "left": case "right": case "center": return 0.225;
        default: return 0.1875;
    }
}
interface KeypointLayerProps {
    pointSource: "keypoints" | "modelLandmarks" | "mappedKeypoints";
    color: Color | "bySide";
    radius: number | "byBodyPart";
    statsKey: "rawKeypoints" | "landmarks" | "mappedKeypoints";
    inspectionKind: "keypoint" | "landmark" | "mapped keypoint";
}
interface PointBatch {
    frameIndex: number;
    rows: Int32Array;
    slots: Uint32Array;
    radii: Float32Array;
    colors: Float32Array;
}

function KeypointLayer({pointSource, color, radius, statsKey, inspectionKind}: KeypointLayerProps) {
    const source = useKeypointsSource();
    const definitions = useModelDefinitionsById();
    const {statsRef} = useViewportState();
    const {invalidate} = useThree();
    const meshRef = useRef<InstancedMesh>(null);
    const rawRef = useRef<KeypointsFrame | null>(null);
    const modelsRef = useRef<ResolvedModelFrame[]>([]);
    const dirtyRef = useRef(false);
    const layoutRef = useRef<PreparedModel[] | null>(null);
    const rawNamesRef = useRef<readonly string[] | undefined>(undefined);
    const definitionsRef = useRef(definitions.current);
    const slotsRef = useRef(new Map<string, number>());
    const pickingRef = useRef(new Map<number, InspectionTarget>());
    const batchesRef = useRef<PointBatch[]>([]);
    const visibilityRef = useRef(new Uint8Array(MAX_POINTS));
    const geo = useMemo(() => new SphereGeometry(50, 4, 3), []);
    const mat = useMemo(() => new MeshBasicMaterial({color: "#ffffff"}), []);
    useEffect(() => () => {geo.dispose(); mat.dispose();}, [geo, mat]);
    useEffect(() => {
        const changed = () => {dirtyRef.current = true; invalidate();};
        if (pointSource === "keypoints") return source.subscribeToKeypoints(frame => {rawRef.current = frame; changed();});
        return source.subscribeToModelFrames(models => {modelsRef.current = models; changed();});
    }, [source, pointSource, invalidate]);
    useEffect(() => {
        const mesh = meshRef.current;
        if (!mesh) return;
        ensureInstanceBuffers(mesh, MAX_POINTS);
        registerPickingMesh(mesh, {kind: inspectionKind, instanceTargets: pickingRef.current});
        return () => unregisterPickingMesh(mesh);
    }, [inspectionKind]);

    useFrame(() => {
        const mesh = meshRef.current;
        if (!mesh) return;
        const models = modelsRef.current, raw = rawRef.current;
        const field = pointSource === "mappedKeypoints" ? "mappedKeypoints" : "landmarks";
        const changed = definitionsRef.current !== definitions.current || (pointSource === "keypoints"
            ? !sameNames(rawNamesRef.current, raw?.pointNames)
            : !layoutRef.current || !preparedModelsMatch(layoutRef.current, models, definitions.current));
        if (changed) {
            definitionsRef.current = definitions.current;
            rawNamesRef.current = raw?.pointNames;
            layoutRef.current = prepareModels(models, definitions.current);
            const declaredCount = pointSource === "keypoints" ? raw?.pointNames.length ?? 0
                : models.reduce((count, model) => count + (model[field]?.names.length ?? 0), 0);
            // Retain slots across ordinary disappearance/reordering, but bound historical
            // names when switching repeatedly between unrelated recordings/layouts.
            if (slotsRef.current.size + declaredCount > Math.max(MAX_POINTS, declaredCount * 2)) {
                slotsRef.current.clear();
                pickingRef.current.clear();
            }
            const batches: PointBatch[] = [];
            const add = (names: readonly string[], frameIndex: number, identity: string, hints?: Record<string, Color>) => {
                const rows: number[] = [], slots: number[] = [], radii: number[] = [], colors: number[] = [];
                names.forEach((name, row) => {
                    if (classifyPointName(name) === 'face') return;
                    const key = JSON.stringify([identity, name]);
                    let slot = slotsRef.current.get(key);
                    if (slot === undefined) {
                        slot = slotsRef.current.size;
                        slotsRef.current.set(key, slot);
                        const model = models[frameIndex];
                        pickingRef.current.set(slot, inspectionKind === "keypoint" ? {kind: "keypoint", name}
                            : {kind: inspectionKind, name, modelId: model.modelId, instanceId: model.instanceId});
                    }
                    const rgb = color === "bySide" ? getPointStyle(name, hints).color : color;
                    rows.push(row); slots.push(slot); radii.push(radius === "byBodyPart" ? getKeypointRadius(name) : radius);
                    colors.push(rgb.r, rgb.g, rgb.b);
                });
                batches.push({frameIndex, rows: Int32Array.from(rows), slots: Uint32Array.from(slots), radii: Float32Array.from(radii), colors: Float32Array.from(colors)});
            };
            if (pointSource === "keypoints") add(raw?.pointNames ?? [], -1, "raw");
            else for (let i = 0; i < models.length; i++) {
                const model = models[i], hints: Record<string, Color> = {};
                for (const group of definitions.current.get(model.modelId)?.landmark_groups ?? []) {
                    const rgb = new Color(group.color);
                    for (const name of group.landmark_names) hints[name] = rgb;
                }
                add(model[field]?.names ?? [], i, JSON.stringify([model.modelId, model.instanceId]), hints);
            }
            batchesRef.current = batches;
            ensureInstanceBuffers(mesh, slotsRef.current.size);
            // Historical slots retain picking identity, but hidden trailing slots need
            // not be submitted to the GPU when their model is absent.
            let activeExtent = 0;
            for (const batch of batches) for (const slot of batch.slots) activeExtent = Math.max(activeExtent, slot + 1);
            mesh.count = activeExtent;
            visibilityRef.current = new Uint8Array(mesh.instanceMatrix.count);
            dirtyRef.current = true;
        }
        if (!dirtyRef.current) return;
        const matrices = mesh.instanceMatrix.array as Float32Array;
        const colors = mesh.instanceColor!.array as Float32Array;
        let count = 0, colorsChanged = changed;
        for (const batch of batchesRef.current) {
            const points = batch.frameIndex < 0 ? null : models[batch.frameIndex]?.[field];
            const data = batch.frameIndex < 0 ? raw?.interleaved : points?.data;
            const stride = points?.stride ?? 3, coordinates = points?.coordinateOffsets ?? XYZ_OFFSETS;
            for (let i = 0; i < batch.rows.length; i++) {
                const slot = batch.slots[i], m = slot * 16, c = slot * 3, offset = batch.rows[i] * stride;
                const visible = finitePoint(data, offset, coordinates);
                if (visible) {
                    const scale = batch.radii[i];
                    matrices[m] = matrices[m + 5] = matrices[m + 10] = scale;
                    matrices[m + 12] = data![offset + coordinates[0]]; matrices[m + 13] = data![offset + coordinates[1]]; matrices[m + 14] = data![offset + coordinates[2]];
                    count++;
                } else hideMatrix(matrices, m);
                if (visibilityRef.current[slot] !== +visible || changed) {
                    colors[c] = visible ? batch.colors[i * 3] : 0;
                    colors[c + 1] = visible ? batch.colors[i * 3 + 1] : 0;
                    colors[c + 2] = visible ? batch.colors[i * 3 + 2] : 0;
                    visibilityRef.current[slot] = +visible; colorsChanged = true;
                }
            }
        }
        mesh.instanceMatrix.needsUpdate = true;
        if (colorsChanged) mesh.instanceColor!.needsUpdate = true;
        dirtyRef.current = false;
        statsRef.current[statsKey] = count;
    });
    return <instancedMesh ref={meshRef} args={[geo, mat, MAX_POINTS]} frustumCulled={false}/>;
}

export function KeypointsRenderer() {
    const { visibility } = useViewportState();

    return (
        <>
            {visibility.rawKeypoints && (
                <KeypointLayer
                    pointSource="keypoints"
                    color={RAW_KEYPOINT_COLOR}
                    radius="byBodyPart"
                    statsKey="rawKeypoints"
                    inspectionKind="keypoint"
                />
            )}
            {visibility.mappedKeypoints && (
                <KeypointLayer
                    pointSource="mappedKeypoints"
                    color={MAPPED_KEYPOINT_COLOR}
                    radius={MAPPED_KEYPOINT_RADIUS}
                    statsKey="mappedKeypoints"
                    inspectionKind="mapped keypoint"
                />
            )}
            {visibility.landmarks && (
                <KeypointLayer
                    pointSource="modelLandmarks"
                    color="bySide"
                    radius="byBodyPart"
                    statsKey="landmarks"
                    inspectionKind="landmark"
                />
            )}
        </>
    );
}
