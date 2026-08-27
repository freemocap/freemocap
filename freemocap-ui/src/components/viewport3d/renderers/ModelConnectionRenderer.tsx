// ModelConnectionRenderer.tsx
//
// The ONE connection renderer. Draws every edge of every tracked model this frame:
//
//   - SEGMENT edges — parent origin -> child origin, from the model's `connections`
//     (the rest-pose parent tree), plotted against SEGMENT_ORIGINS.
//   - LANDMARK edges — from the model's `landmark_connections` groups, plotted against
//     LANDMARKS_3D. These are the only kind of edge a one-segment model has, which is what
//     draws a charuco board's grid and its aruco quads.
//
// Everything it draws is declared by the model and arrives over the wire, colours included
// (the backend resolves them from the palette, so swapping the palette recolours every
// client at once). Nothing here parses a name to recover structure, and nothing is
// hardcoded per object: the board, the skull outline and the eye lines are all just
// connection groups.
//
// It iterates models rather than reading `models[0]`, so a tracked person and a tracked
// board draw side by side.
//
// Runs ALONGSIDE RigidBodyBoneRenderer (the oriented cylinders); these are the
// overlay-style joint lines.

import { useEffect, useMemo, useRef, useState } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { InterleavedBufferAttribute, Vector2 } from "three";
import { LineSegments2, LineSegmentsGeometry, LineMaterial } from "three-stdlib";
import { useKeypointsSource, useModelDefinitionsById } from "../KeypointsSourceContext";
import type { ResolvedModelFrame } from "@/services/server/transport/frame-types";
import type { ModelDefinition } from "@/services/server/transport/message-contract";
import { BONE_SIDE_COLORS, classifyBone } from "./RigidBodyBoneInstances";

const LINE_WIDTH = 2;
/** Parked far off-screen — an edge whose endpoints are missing this frame. */
const HIDDEN_COORDINATE = 1e5;

type Rgb = readonly [number, number, number];

/** "#rrggbb" -> normalized rgb. The wire always carries a resolved colour, so a group
 *  that reaches here without one is a backend defect rather than something to guess at. */
function parseHexColor(hex: string): Rgb {
    const value = Number.parseInt(hex.replace("#", ""), 16);
    return [
        ((value >> 16) & 0xff) / 255,
        ((value >> 8) & 0xff) / 255,
        (value & 0xff) / 255,
    ];
}

/** Which array an edge's endpoints index into. */
type EndpointSource = "segmentOrigins" | "landmarks";

interface PlannedEdge {
    modelId: string;
    source: EndpointSource;
    startIndex: number;
    endIndex: number;
    color: Rgb;
}

/** The complete edge list for a set of models — rebuilt only when the MODELS change, so
 *  the per-frame path is a pure index-and-copy with no name lookups in it. */
function planEdgesForModels(
    models: ResolvedModelFrame[],
    definitionsById: Map<string, ModelDefinition>,
): PlannedEdge[] {
    const planned: PlannedEdge[] = [];
    for (const entry of models) {
        const definition = definitionsById.get(entry.modelId);
        if (!definition) continue;
        const segmentIndexByName = new Map(definition.segments.map((s, i) => [s.name, i]));
        const landmarkIndexByName = new Map(definition.landmarks.map((l, i) => [l.name, i]));

        for (const [parent, child] of definition.connections) {
            const startIndex = segmentIndexByName.get(parent);
            const endIndex = segmentIndexByName.get(child);
            if (startIndex === undefined || endIndex === undefined) continue;
            // The edge IS the child bone hanging off its parent's origin, so the child is
            // what it represents — which puts a hand's edges in the hand's colour rather
            // than the forearm's. Reading BONE_SIDE_COLORS rather than keeping a second
            // palette here keeps the lines and the bone meshes from drifting apart.
            planned.push({
                modelId: entry.modelId,
                source: "segmentOrigins",
                startIndex,
                endIndex,
                color: BONE_SIDE_COLORS[classifyBone(child)],
            });
        }

        for (const group of definition.landmark_connections) {
            const color = parseHexColor(group.color);
            for (const [start, end] of group.pairs) {
                const startIndex = landmarkIndexByName.get(start);
                const endIndex = landmarkIndexByName.get(end);
                if (startIndex === undefined || endIndex === undefined) continue;
                planned.push({
                    modelId: entry.modelId,
                    source: "landmarks",
                    startIndex,
                    endIndex,
                    color,
                });
            }
        }
    }
    return planned;
}

/** Identity of the MODEL SET — what a replan depends on. A new board size or a second
 *  tracked object changes this; a new frame of the same models does not. */
function modelSetSignature(models: ResolvedModelFrame[]): string {
    return models.map((m) => m.modelId).join("|");
}

function isFinitePoint(data: Float32Array, index: number): boolean {
    const offset = index * 3;
    return (
        Number.isFinite(data[offset]) &&
        Number.isFinite(data[offset + 1]) &&
        Number.isFinite(data[offset + 2])
    );
}

export function ModelConnectionRenderer() {
    const { subscribeToModelFrames } = useKeypointsSource();
    const definitionsById = useModelDefinitionsById();
    const { size } = useThree();

    const [plannedEdges, setPlannedEdges] = useState<PlannedEdge[]>([]);
    const modelFramesRef = useRef<ResolvedModelFrame[] | null>(null);
    const signatureRef = useRef<string>("");
    const dirtyRef = useRef(false);

    useEffect(() => {
        return subscribeToModelFrames((models) => {
            modelFramesRef.current = models;
            // Replanned on a change of the MODEL SET or the definitions behind it — never
            // per frame. `definitionsRevision` is what makes a late-arriving definition
            // trigger the replan the frame data alone cannot.
            const signature = `${modelSetSignature(models)}#${definitionsById.current.size}`;
            if (signature !== signatureRef.current) {
                signatureRef.current = signature;
                setPlannedEdges(planEdgesForModels(models, definitionsById.current));
            }
            dirtyRef.current = true;
        });
    }, [subscribeToModelFrames, definitionsById]);

    // Geometry sized to the edge count (at least one, so LineSegmentsGeometry stays valid).
    const edgeCount = plannedEdges.length || 1;
    const geometry = useMemo(() => {
        const created = new LineSegmentsGeometry();
        created.setPositions(new Float32Array(edgeCount * 2 * 3).fill(HIDDEN_COORDINATE));
        created.setColors(new Float32Array(edgeCount * 2 * 3).fill(0));
        return created;
    }, [edgeCount]);
    const material = useMemo(
        () =>
            new LineMaterial({
                vertexColors: true,
                transparent: true,
                opacity: 0.85,
                linewidth: LINE_WIDTH,
                resolution: new Vector2(size.width, size.height),
            }),
        [size.width, size.height],
    );
    const [lineObject] = useState(() => new LineSegments2());

    useEffect(() => () => { geometry.dispose(); material.dispose(); }, [geometry, material]);

    useFrame(() => {
        if (!dirtyRef.current) return;
        const models = modelFramesRef.current;
        if (!models) return;

        const positionAttribute = geometry.attributes.instanceStart as InterleavedBufferAttribute;
        const colorAttribute = geometry.attributes.instanceColorStart as InterleavedBufferAttribute;
        const positions = positionAttribute.data.array as Float32Array;
        const colors = colorAttribute.data.array as Float32Array;

        const pointsByModelId = new Map<string, Record<EndpointSource, Float32Array | null>>();
        for (const entry of models) {
            pointsByModelId.set(entry.modelId, {
                segmentOrigins: entry.segmentOrigins?.data ?? null,
                landmarks: entry.landmarks?.data ?? null,
            });
        }

        for (let i = 0; i < plannedEdges.length; i++) {
            const edge = plannedEdges[i];
            const base = i * 6;
            const points = pointsByModelId.get(edge.modelId)?.[edge.source] ?? null;

            const drawable =
                points !== null &&
                isFinitePoint(points, edge.startIndex) &&
                isFinitePoint(points, edge.endIndex);

            if (!drawable) {
                for (let j = 0; j < 6; j++) {
                    positions[base + j] = HIDDEN_COORDINATE;
                    colors[base + j] = 0;
                }
                continue;
            }

            const startOffset = edge.startIndex * 3;
            const endOffset = edge.endIndex * 3;
            positions[base] = points![startOffset];
            positions[base + 1] = points![startOffset + 1];
            positions[base + 2] = points![startOffset + 2];
            positions[base + 3] = points![endOffset];
            positions[base + 4] = points![endOffset + 1];
            positions[base + 5] = points![endOffset + 2];
            const [r, g, b] = edge.color;
            colors[base] = r; colors[base + 1] = g; colors[base + 2] = b;
            colors[base + 3] = r; colors[base + 4] = g; colors[base + 5] = b;
        }

        positionAttribute.needsUpdate = true;
        colorAttribute.needsUpdate = true;
        dirtyRef.current = false;
    });

    return (
        <primitive object={lineObject} frustumCulled={false}>
            <primitive object={geometry} attach="geometry" />
            <primitive object={material} attach="material" />
        </primitive>
    );
}
