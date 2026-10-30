import { useEffect, useMemo, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { InterleavedBufferAttribute } from "three";
import { LineSegments2, LineSegmentsGeometry, LineMaterial } from "three-stdlib";
import { useKeypointsSource, useModelDefinitionsById } from "../KeypointsSourceContext";
import type { ResolvedModelFrame } from "@/services/server/transport/frame-types";
import { BONE_SIDE_COLORS, classifyBone } from "./RigidBodyBoneInstances";
import { useViewportState } from "../scene/ViewportStateContext";
import { finitePoint, XYZ_OFFSETS, prepareModels, preparedModelsMatch, type PreparedModel } from "./prepared-models";

const HIDDEN_COORDINATE = 1e5;
interface EdgeBatch {
    frameIndex: number;
    source: "segmentOrigins" | "landmarks";
    baseEdge: number;
    rows: Int32Array;
    colors: Float32Array;
}
function prepareEdges(models: PreparedModel[]): EdgeBatch[] {
    const batches: EdgeBatch[] = [];
    let baseEdge = 0;
    for (const model of models) {
        const definition = model.definition;
        if (!definition) continue;
        const segments = new Map(definition.segments.map((s, i) => [s.name, model.originRows[i]]));
        const landmarks = new Map(definition.landmarks.map((s, i) => [s.name, model.landmarkRows[i]]));
        for (const source of ["segmentOrigins", "landmarks"] as const) {
            const rows: number[] = [], colors: number[] = [];
            const append = (pairs: readonly (readonly [string, string])[], indices: Map<string, number>, rgb?: readonly number[]) => {
                for (const [start, end] of pairs) {
                    const a = indices.get(start), b = indices.get(end);
                    if (a === undefined || b === undefined) continue;
                    rows.push(a, b);
                    const color = rgb ?? BONE_SIDE_COLORS[classifyBone(end)];
                    colors.push(...color, ...color);
                }
            };
            if (source === "segmentOrigins") append(definition.connections, segments);
            else for (const group of definition.landmark_connections) {
                const hex = Number.parseInt(group.color.replace("#", ""), 16);
                append(group.pairs, landmarks, [((hex >> 16) & 255) / 255, ((hex >> 8) & 255) / 255, (hex & 255) / 255]);
            }
            batches.push({frameIndex: model.frameIndex, source, baseEdge, rows: Int32Array.from(rows), colors: Float32Array.from(colors)});
            baseEdge += rows.length / 2;
        }
    }
    return batches;
}
export function ModelConnectionRenderer() {
    const {subscribeToModelFrames} = useKeypointsSource();
    const definitions = useModelDefinitionsById();
    const {statsRef} = useViewportState();
    const {size} = useThree();
    const framesRef = useRef<ResolvedModelFrame[]>([]);
    const layoutRef = useRef<PreparedModel[] | null>(null);
    const batchesRef = useRef<EdgeBatch[]>([]);
    const visibleRef = useRef(new Uint8Array());
    const dirtyRef = useRef(false);
    const geometry = useMemo(() => {
        const g = new LineSegmentsGeometry();
        g.setPositions(new Float32Array(6).fill(HIDDEN_COORDINATE)); g.setColors(new Float32Array(6)); return g;
    }, []);
    const material = useMemo(() => new LineMaterial({vertexColors: true, transparent: true, opacity: 0.85, linewidth: 2}), []);
    const object = useMemo(() => new LineSegments2(geometry, material), [geometry, material]);
    useEffect(() => {material.resolution.set(size.width, size.height);}, [material, size.width, size.height]);
    useEffect(() => () => {geometry.dispose(); material.dispose();}, [geometry, material]);
    useEffect(() => subscribeToModelFrames(frames => {framesRef.current = frames; dirtyRef.current = true;}), [subscribeToModelFrames]);
    useFrame(() => {
        const frames = framesRef.current;
        if (!layoutRef.current || !preparedModelsMatch(layoutRef.current, frames, definitions.current)) {
            layoutRef.current = prepareModels(frames, definitions.current);
            const batches = prepareEdges(layoutRef.current);
            batchesRef.current = batches;
            const count = batches.reduce((sum, batch) => sum + batch.rows.length / 2, 0);
            // Release replaced GPU attributes on schema changes, including equal-size changes.
            geometry.dispose();
            geometry.setPositions(new Float32Array(Math.max(1, count) * 6).fill(HIDDEN_COORDINATE));
            geometry.setColors(new Float32Array(Math.max(1, count) * 6));
            geometry.instanceCount = count;
            visibleRef.current = new Uint8Array(count);
            dirtyRef.current = true;
        }
        if (!dirtyRef.current) return;
        const position = geometry.attributes.instanceStart as InterleavedBufferAttribute;
        const color = geometry.attributes.instanceColorStart as InterleavedBufferAttribute;
        const positions = position.data.array as Float32Array, colors = color.data.array as Float32Array;
        let drawn = 0, colorsChanged = false;
        for (const batch of batchesRef.current) {
            const points = frames[batch.frameIndex][batch.source]; const data = points?.data; const stride = points?.stride ?? 3, coordinates = points?.coordinateOffsets ?? XYZ_OFFSETS;
            for (let i = 0; i < batch.rows.length / 2; i++) {
                const edge = batch.baseEdge + i, base = edge * 6;
                const a = batch.rows[i * 2] * stride, b = batch.rows[i * 2 + 1] * stride;
                const visible = finitePoint(data, a, coordinates) && finitePoint(data, b, coordinates);
                if (visible) {
                    positions[base] = data![a + coordinates[0]]; positions[base + 1] = data![a + coordinates[1]]; positions[base + 2] = data![a + coordinates[2]];
                    positions[base + 3] = data![b + coordinates[0]]; positions[base + 4] = data![b + coordinates[1]]; positions[base + 5] = data![b + coordinates[2]];
                    drawn++;
                } else positions.fill(HIDDEN_COORDINATE, base, base + 6);
                if (visibleRef.current[edge] !== +visible) {
                    for (let c = 0; c < 6; c++) colors[base + c] = visible ? batch.colors[i * 6 + c] : 0;
                    visibleRef.current[edge] = +visible; colorsChanged = true;
                }
            }
        }
        position.data.needsUpdate = true;
        if (colorsChanged) color.data.needsUpdate = true;
        statsRef.current.boneLines = drawn;
        dirtyRef.current = false;
    });
    return <primitive object={object} frustumCulled={false}/>;
}
