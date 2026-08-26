// SegmentAxesRenderer.tsx
//
// Per-segment orientation triads: three short lines (x red, y green, z blue)
// at each segment's world origin, rotated by the segment's ROTATIONS_WORLD
// quaternion. This is the same diagnostic the skellyforge viewer ships —
// it shows which way each rigid body's local frame actually points, which is
// the fastest way to spot a roll or convention bug.
//
// Cost profile: ONE LineSegments draw call for the whole skeleton. Positions
// are written into a preallocated buffer per dirty frame (61 segments × 3
// axes = 183 short vectors of arithmetic) and colors are static vertex
// attributes set once — no allocations, no material churn, nothing to GC.

import { useCallback, useEffect, useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import {
    BufferAttribute,
    BufferGeometry,
    LineBasicMaterial,
    LineSegments,
    Quaternion,
    Vector3,
} from "three";
import { useKeypointsSource, type KeypointsFrame } from "../KeypointsSourceContext";
import type { RotationsFrame } from "@/services/server/transport/frame-types";
import type { ModelDefinition } from "@/services/server/transport/message-contract";

const MAX_SEGMENTS = 256;
const VERTICES_PER_SEGMENT = 6; // 3 axes × 2 endpoints
const FLOATS_PER_SEGMENT = VERTICES_PER_SEGMENT * 3;

// Vertex-color RGB per axis index (0=x, 1=y, 2=z). Full-saturation primaries,
// kept just under the bloom pass threshold so they stay crisp.
const AXIS_COLORS: readonly [number, number, number][] = [
    [1.0, 0.3, 0.25],
    [0.35, 1.0, 0.3],
    [0.3, 0.55, 1.0],
];

// Axis length scales with each segment's rest length so a phalanx gets a
// stubby triad and a thigh gets a long one, clamped to stay legible.
const AXIS_LENGTH_FRACTION = 0.3;
const MIN_AXIS_LENGTH_MM = 7.5;
const MAX_AXIS_LENGTH_MM = 50;

interface SegmentAxisTable {
    segmentCount: number;
    /** Per-segment triad arm length in mm. */
    axisLengthsMm: Float32Array;
}

// Module-level scratch (zero per-frame allocation).
const _quaternion = new Quaternion();
const _axis = new Vector3();

function buildAxisTable(model: ModelDefinition): SegmentAxisTable {
    const segmentCount = Math.min(model.segments.length, MAX_SEGMENTS);
    const axisLengthsMm = new Float32Array(segmentCount);
    for (let i = 0; i < segmentCount; i++) {
        const lengthMm = model.segments[i].length_mm;
        const scaled = Number.isFinite(lengthMm) && lengthMm > 0 ? lengthMm * AXIS_LENGTH_FRACTION : 50;
        axisLengthsMm[i] = Math.min(Math.max(scaled, MIN_AXIS_LENGTH_MM), MAX_AXIS_LENGTH_MM);
    }
    return { segmentCount, axisLengthsMm };
}

export function SegmentAxesRenderer() {
    const { subscribeToSkeleton, subscribeToRotations, subscribeToModels, getModels } =
        useKeypointsSource();
    const lineRef = useRef<LineSegments>(null);
    const skeletonRef = useRef<KeypointsFrame | null>(null);
    const rotationsRef = useRef<RotationsFrame | null>(null);
    const tableRef = useRef<SegmentAxisTable | null>(null);
    const dirtyRef = useRef(false);

    // Fixed-capacity buffers: positions rewritten per frame, colors written once.
    const geometry = useMemo(() => {
        const geometry = new BufferGeometry();
        const positions = new Float32Array(MAX_SEGMENTS * FLOATS_PER_SEGMENT);
        const colors = new Float32Array(MAX_SEGMENTS * FLOATS_PER_SEGMENT);
        for (let segmentIdx = 0; segmentIdx < MAX_SEGMENTS; segmentIdx++) {
            for (let axisIdx = 0; axisIdx < 3; axisIdx++) {
                const color = AXIS_COLORS[axisIdx];
                const base = (segmentIdx * 3 + axisIdx) * 6;
                // Both endpoints of each axis share its color.
                for (let endpoint = 0; endpoint < 2; endpoint++) {
                    const offset = base + endpoint * 3;
                    colors[offset] = color[0];
                    colors[offset + 1] = color[1];
                    colors[offset + 2] = color[2];
                }
            }
        }
        geometry.setAttribute("position", new BufferAttribute(positions, 3));
        geometry.setAttribute("color", new BufferAttribute(colors, 3));
        return geometry;
    }, []);

    const material = useMemo(
        () => new LineBasicMaterial({ vertexColors: true }),
        [],
    );

    useEffect(
        () => () => {
            geometry.dispose();
            material.dispose();
        },
        [geometry, material],
    );

    const applyTable = useCallback(() => {
        const geometryToBound = geometry;
        const table = tableRef.current;
        if (!table) return;
        geometryToBound.setDrawRange(0, table.segmentCount * VERTICES_PER_SEGMENT);
    }, [geometry]);

    useEffect(() => {
        const rebuild = (models: ModelDefinition[]) => {
            if (models.length === 0) return;
            tableRef.current = buildAxisTable(models[0]);
            applyTable();
        };
        const unsubscribe = subscribeToModels ? subscribeToModels(rebuild) : () => {};
        const existing = getModels?.();
        if (existing && existing.length > 0) rebuild(existing);
        return unsubscribe;
    }, [subscribeToModels, getModels, applyTable]);

    useEffect(() => {
        return subscribeToSkeleton((frame) => {
            skeletonRef.current = frame;
            dirtyRef.current = true;
        });
    }, [subscribeToSkeleton]);

    useEffect(() => {
        if (!subscribeToRotations) return;
        return subscribeToRotations((frame) => {
            rotationsRef.current = frame;
            dirtyRef.current = true;
        });
    }, [subscribeToRotations]);

    useFrame(() => {
        const line = lineRef.current;
        const table = tableRef.current;
        if (!line || !table || !dirtyRef.current) return;
        const skeleton = skeletonRef.current;
        const rotations = rotationsRef.current;
        if (!skeleton || !rotations) return;

        const positionAttribute = geometry.getAttribute("position") as BufferAttribute;
        const positions = positionAttribute.array as Float32Array;

        for (let segmentIdx = 0; segmentIdx < table.segmentCount; segmentIdx++) {
            const originOffset = segmentIdx * 3;
            const quaternionOffset = segmentIdx * 4;
            const ox = skeleton.interleaved[originOffset];
            const oy = skeleton.interleaved[originOffset + 1];
            const oz = skeleton.interleaved[originOffset + 2];
            const qw = rotations.worldQuaternions[quaternionOffset];
            const qx = rotations.worldQuaternions[quaternionOffset + 1];
            const qy = rotations.worldQuaternions[quaternionOffset + 2];
            const qz = rotations.worldQuaternions[quaternionOffset + 3];

            const finiteOrigin =
                Number.isFinite(ox) && Number.isFinite(oy) && Number.isFinite(oz);
            const finiteQuaternion =
                Number.isFinite(qw) && Number.isFinite(qx) && Number.isFinite(qy) && Number.isFinite(qz);

            if (!finiteOrigin || !finiteQuaternion) {
                // Collapse the triad to a degenerate point - invisible, no branchy hide logic.
                collapseSegment(positions, segmentIdx);
                continue;
            }

            // three.js Quaternion.set is (x, y, z, w) — VECTOR first. The wire
            // carries scalar-first [w, x, y, z], so the components are swapped
            // here on purpose; passing them straight through scrambles the
            // rotation into something that looks like untracked axes.
            _quaternion.set(qx, qy, qz, qw);
            const armLength = table.axisLengthsMm[segmentIdx];
            const segmentBase = segmentIdx * FLOATS_PER_SEGMENT;

            for (let axisIdx = 0; axisIdx < 3; axisIdx++) {
                _axis.set(
                    axisIdx === 0 ? 1 : 0,
                    axisIdx === 1 ? 1 : 0,
                    axisIdx === 2 ? 1 : 0,
                ).applyQuaternion(_quaternion);

                const writeBase = segmentBase + axisIdx * 6;
                positions[writeBase] = ox;
                positions[writeBase + 1] = oy;
                positions[writeBase + 2] = oz;
                positions[writeBase + 3] = ox + _axis.x * armLength;
                positions[writeBase + 4] = oy + _axis.y * armLength;
                positions[writeBase + 5] = oz + _axis.z * armLength;
            }
        }

        positionAttribute.needsUpdate = true;
        dirtyRef.current = false;
    });

    return (
        <lineSegments ref={lineRef} geometry={geometry} material={material} frustumCulled={false} />
    );
}

/** Zero out one segment's six vertices so nothing draws for it. */
function collapseSegment(positions: Float32Array, segmentIdx: number): void {
    const base = segmentIdx * FLOATS_PER_SEGMENT;
    for (let fill = 0; fill < FLOATS_PER_SEGMENT; fill += 3) {
        positions[base + fill] = 0;
        positions[base + fill + 1] = 0;
        positions[base + fill + 2] = 0;
    }
}
