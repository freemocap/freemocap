import { useEffect, useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { BufferAttribute, BufferGeometry, LineBasicMaterial } from "three";
import { useKeypointsSource, useModelDefinitionsById } from "../KeypointsSourceContext";
import type { ResolvedModelFrame } from "@/services/server/transport/frame-types";
import { AXIS_HEX, hexToRgb01 } from "../helpers/layer-colors";
import { finitePoint, XYZ_OFFSETS, prepareModels, preparedModelsMatch, type PreparedModel } from "./prepared-models";
import { writeRotation } from "./prepared-bones";

const AXIS_COLORS = AXIS_HEX.map(hexToRgb01);
interface PreparedAxes {model: PreparedModel; baseSlot: number; scale: number | null; lengths: Float32Array}
export function SegmentAxesRenderer() {
    const {subscribeToModelFrames} = useKeypointsSource();
    const definitions = useModelDefinitionsById();
    const framesRef = useRef<ResolvedModelFrame[]>([]);
    const layoutRef = useRef<PreparedModel[] | null>(null);
    const axesRef = useRef<PreparedAxes[]>([]);
    const dirtyRef = useRef(false);
    const rotation = useMemo(() => new Float64Array(9), []);
    const geometry = useMemo(() => new BufferGeometry(), []);
    const material = useMemo(() => new LineBasicMaterial({vertexColors: true}), []);
    useEffect(() => () => {geometry.dispose(); material.dispose();}, [geometry, material]);
    useEffect(() => subscribeToModelFrames(frames => {framesRef.current = frames; dirtyRef.current = true;}), [subscribeToModelFrames]);
    useFrame(() => {
        const frames = framesRef.current;
        if (!layoutRef.current || !preparedModelsMatch(layoutRef.current, frames, definitions.current)) {
            layoutRef.current = prepareModels(frames, definitions.current);
            let count = 0;
            axesRef.current = layoutRef.current.map(model => {
                const lengths = new Float32Array(model.definition?.segments.length ?? 0);
                const axes = {model, baseSlot: count, scale: Number.NaN, lengths}; count += lengths.length; return axes;
            });
            const colors = new Float32Array(count * 18);
            for (let i = 0; i < count; i++) for (let axis = 0; axis < 3; axis++) {
                colors.set(AXIS_COLORS[axis], i * 18 + axis * 6); colors.set(AXIS_COLORS[axis], i * 18 + axis * 6 + 3);
            }
            geometry.dispose();
            geometry.setAttribute("position", new BufferAttribute(new Float32Array(count * 18), 3));
            geometry.setAttribute("color", new BufferAttribute(colors, 3));
            geometry.setDrawRange(0, count * 6);
            dirtyRef.current = true;
        }
        if (!dirtyRef.current) return;
        const positions = geometry.attributes.position.array as Float32Array;
        for (const axes of axesRef.current) {
            const {model, lengths, baseSlot} = axes, frame = frames[model.frameIndex];
            const scale = frame.fittedScaleMm == null ? null : Math.round(frame.fittedScaleMm);
            if (axes.scale !== scale) {
                axes.scale = scale;
                for (let i = 0; i < lengths.length; i++) {
                    const proportion = model.definition!.segments[i].length_proportion;
                    const length = frame.fittedScaleMm != null && frame.fittedScaleMm > 0 && Number.isFinite(proportion) && proportion > 0
                        ? proportion * frame.fittedScaleMm * 0.3 : 50;
                    lengths[i] = Math.min(Math.max(length, 7.5), 50);
                }
            }
            const origins = frame.segmentOrigins?.data, quats = frame.rotations?.worldQuaternions; const stride = frame.segmentOrigins?.stride ?? 3, coordinates = frame.segmentOrigins?.coordinateOffsets ?? XYZ_OFFSETS;
            for (let i = 0; i < lengths.length; i++) {
                const o = model.originRows[i] * stride, q = model.rotationRows[i] * 4, base = (baseSlot + i) * 18;
                if (!finitePoint(origins, o, coordinates) || !finitePoint(quats, q) || !Number.isFinite(quats?.[q + 3])) {
                    positions.fill(0, base, base + 18); continue;
                }
                writeRotation(rotation, quats![q], quats![q + 1], quats![q + 2], quats![q + 3]);
                for (let axis = 0; axis < 3; axis++) for (let coordinate = 0; coordinate < 3; coordinate++) {
                    positions[base + axis * 6 + coordinate] = origins![o + coordinates[coordinate]];
                    positions[base + axis * 6 + 3 + coordinate] = origins![o + coordinates[coordinate]] + rotation[coordinate * 3 + axis] * lengths[i];
                }
            }
        }
        geometry.attributes.position.needsUpdate = true; dirtyRef.current = false;
    });
    return <lineSegments geometry={geometry} material={material} frustumCulled={false}/>;
}
