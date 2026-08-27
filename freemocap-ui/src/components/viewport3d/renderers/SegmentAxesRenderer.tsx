// SegmentAxesRenderer.tsx
//
// Per-segment orientation triads: three short lines (x red, y green, z blue)
// at each segment's world origin, rotated by the segment's ROTATIONS_WORLD
// quaternion. This is the same diagnostic the skellyforge viewer ships —
// it shows which way each rigid body's local frame actually points, which is
// the fastest way to spot a roll or convention bug.
//
// It draws EVERY model in the frame, each occupying a contiguous block of segment slots
// in the shared buffer — so a tracked person and a tracked charuco board both show their
// frames without one overwriting the other.
//
// Cost profile: ONE LineSegments draw call for every model at once. Positions are written
// into a preallocated buffer per dirty frame (61 segments × 3 axes = 183 short vectors of
// arithmetic) and colors are static vertex attributes set once — no allocations, no
// material churn, nothing to GC.

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
import { useKeypointsSource, useModelDefinitionsById } from "../KeypointsSourceContext";
import type { ResolvedModelFrame } from "@/services/server/transport/frame-types";
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

/** One model's triads: where its block of segment slots starts, and how long each of its
 *  arms should be. */
interface SegmentAxisBlock {
    modelId: string;
    baseSlot: number;
    segmentCount: number;
    /** Per-segment triad arm length in mm. */
    axisLengthsMm: Float32Array;
}

// Module-level scratch (zero per-frame allocation).
const _quaternion = new Quaternion();
const _axis = new Vector3();

/** One block of triads per model, sized from each segment's own size.
 *
 *  A model is dimensionless, so its `length_proportion` only becomes a length once it is
 *  multiplied by that model's fitted scale. Until a fit exists there is no size to scale
 *  by, and every axis takes the same nominal length — which is the honest picture, not a
 *  guess at how big the thing might be. Recomputed whenever a fitted scale changes.
 */
function buildAxisBlocks(
    models: ResolvedModelFrame[],
    definitionsById: Map<string, ModelDefinition>,
): SegmentAxisBlock[] {
    const blocks: SegmentAxisBlock[] = [];
    let nextSlot = 0;
    for (const entry of models) {
        const definition = definitionsById.get(entry.modelId);
        if (!definition) continue;
        const segmentCount = Math.min(definition.segments.length, MAX_SEGMENTS - nextSlot);
        if (segmentCount <= 0) break;
        const fittedScaleMm = entry.fittedScaleMm;
        const axisLengthsMm = new Float32Array(segmentCount);
        for (let i = 0; i < segmentCount; i++) {
            const proportion = definition.segments[i].length_proportion;
            const lengthMm =
                fittedScaleMm != null && fittedScaleMm > 0 &&
                Number.isFinite(proportion) && proportion > 0
                    ? proportion * fittedScaleMm
                    : null;
            const scaled = lengthMm !== null ? lengthMm * AXIS_LENGTH_FRACTION : 50;
            axisLengthsMm[i] = Math.min(Math.max(scaled, MIN_AXIS_LENGTH_MM), MAX_AXIS_LENGTH_MM);
        }
        blocks.push({ modelId: entry.modelId, baseSlot: nextSlot, segmentCount, axisLengthsMm });
        nextSlot += segmentCount;
    }
    return blocks;
}

/** What a rebuild depends on: which models, and each one's fitted scale (the arm lengths
 *  are proportional to it).
 *
 *  The scale is quantised to the millimetre. A live fit moves in the last decimal place
 *  every single frame, so comparing it raw rebuilds every block on every frame to produce
 *  visually identical triads. */
function axisBlockSignature(models: ResolvedModelFrame[]): string {
    return models
        .map((m) => `${m.modelId}:${m.fittedScaleMm == null ? "?" : Math.round(m.fittedScaleMm)}`)
        .join("|");
}

export function SegmentAxesRenderer() {
    const { subscribeToModelFrames } = useKeypointsSource();
    const definitionsById = useModelDefinitionsById();
    const lineRef = useRef<LineSegments>(null);
    const modelFramesRef = useRef<ResolvedModelFrame[] | null>(null);
    const blocksRef = useRef<SegmentAxisBlock[]>([]);
    const signatureRef = useRef<string>("");
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

    const applyBlocks = useCallback(() => {
        const blocks = blocksRef.current;
        const drawnSlots = blocks.reduce((total, b) => total + b.segmentCount, 0);
        geometry.setDrawRange(0, drawnSlots * VERTICES_PER_SEGMENT);
    }, [geometry]);

    useEffect(() => {
        return subscribeToModelFrames((models) => {
            modelFramesRef.current = models;
            // The arm lengths depend on each model's fitted scale as well as on its
            // segments, so the signature carries both — a rebuild is 61 float multiplies
            // and only happens on the frames where the fit actually moved.
            const signature = `${axisBlockSignature(models)}#${definitionsById.current.size}`;
            if (signature !== signatureRef.current) {
                signatureRef.current = signature;
                blocksRef.current = buildAxisBlocks(models, definitionsById.current);
                applyBlocks();
            }
            dirtyRef.current = true;
        });
    }, [subscribeToModelFrames, applyBlocks, definitionsById]);

    useFrame(() => {
        const line = lineRef.current;
        const models = modelFramesRef.current;
        if (!line || !models || !dirtyRef.current) return;

        const positionAttribute = geometry.getAttribute("position") as BufferAttribute;
        const positions = positionAttribute.array as Float32Array;
        const frameByModelId = new Map(models.map((m) => [m.modelId, m]));

        for (const block of blocksRef.current) {
        const entry = frameByModelId.get(block.modelId);
        const origins = entry?.segmentOrigins ?? null;
        const rotations = entry?.rotations ?? null;

        for (let localIdx = 0; localIdx < block.segmentCount; localIdx++) {
            const segmentIdx = block.baseSlot + localIdx;
            const originOffset = localIdx * 3;
            const quaternionOffset = localIdx * 4;
            const ox = origins?.data[originOffset] ?? Number.NaN;
            const oy = origins?.data[originOffset + 1] ?? Number.NaN;
            const oz = origins?.data[originOffset + 2] ?? Number.NaN;
            const qw = rotations?.worldQuaternions[quaternionOffset] ?? Number.NaN;
            const qx = rotations?.worldQuaternions[quaternionOffset + 1] ?? Number.NaN;
            const qy = rotations?.worldQuaternions[quaternionOffset + 2] ?? Number.NaN;
            const qz = rotations?.worldQuaternions[quaternionOffset + 3] ?? Number.NaN;

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
            const armLength = block.axisLengthsMm[localIdx];
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
