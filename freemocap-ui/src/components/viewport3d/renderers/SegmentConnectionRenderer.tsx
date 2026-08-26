// SegmentConnectionRenderer.tsx
//
// Draws the skeleton's segment-origin CONNECTIONS (parent origin -> child
// origin) in 3D, matching the 2D overlay's lines. The edges come straight from
// the self-describing model's `connections` list (the rest-pose parent tree);
// nothing is derived client-side. Segment origins come from SEGMENT_ORIGINS
// (index-keyed in model segment order), so a name->index map built once at
// model time resolves each edge's endpoints.
//
// This runs ALONGSIDE RigidBodyBoneRenderer (the oriented cylinders) and does
// not touch it — the bones stay, and these are the overlay-style joint lines.

import { useEffect, useMemo, useRef, useState } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { InterleavedBufferAttribute, Vector2 } from "three";
import { LineSegments2, LineSegmentsGeometry, LineMaterial } from "three-stdlib";
import { useKeypointsSource, type KeypointsFrame } from "../KeypointsSourceContext";
import type { ModelDefinition } from "@/services/server/transport/message-contract";
import { BONE_SIDE_COLORS, classifyBone } from "./RigidBodyBoneInstances";

const LINE_WIDTH = 2;

/** An edge's color: the CHILD segment's, from the shared bone-color table.
 *
 *  The edge is the child bone hanging off its parent's origin, so the child is what it
 *  represents — which also puts a hand's connections in the hand's color rather than the
 *  forearm's. Reading `BONE_SIDE_COLORS` rather than keeping a second palette here is what
 *  stops the lines and the bone meshes from drifting apart. */
function edgeColor(childSegmentName: string): readonly [number, number, number] {
    return BONE_SIDE_COLORS[classifyBone(childSegmentName)];
}

export function SegmentConnectionRenderer() {
    const { subscribeToSkeleton, subscribeToModels, getModels } = useKeypointsSource();
    const { size } = useThree();

    const [connections, setConnections] = useState<[string, string][]>([]);
    const nameToIndexRef = useRef<Map<string, number>>(new Map());
    const skeletonRef = useRef<KeypointsFrame | null>(null);
    const dirtyRef = useRef(false);

    // Model arrival -> edges + name->index (both static per model).
    useEffect(() => {
        const build = (models: ModelDefinition[]) => {
            const model = models[0];
            if (!model) return;
            setConnections(model.connections ?? []);
            nameToIndexRef.current.clear();
            model.segments.forEach((s, i) => nameToIndexRef.current.set(s.name, i));
            dirtyRef.current = true;
        };
        const unsub = subscribeToModels ? subscribeToModels(build) : () => {};
        const existing = getModels?.();
        if (existing && existing.length > 0) build(existing);
        return unsub;
    }, [subscribeToModels, getModels]);

    useEffect(() => {
        return subscribeToSkeleton((frame) => {
            skeletonRef.current = frame;
            dirtyRef.current = true;
        });
    }, [subscribeToSkeleton]);

    // Geometry sized to the edge count (>= 1 segment so LineSegmentsGeometry is valid).
    const n = connections.length || 1;
    const geo = useMemo(() => {
        const g = new LineSegmentsGeometry();
        g.setPositions(new Float32Array(n * 2 * 3).fill(1e5));
        g.setColors(new Float32Array(n * 2 * 3).fill(0));
        return g;
    }, [n]);
    const mat = useMemo(() => new LineMaterial({
        vertexColors: true,
        transparent: true,
        opacity: 0.85,
        linewidth: LINE_WIDTH,
        resolution: new Vector2(size.width, size.height),
    }), [size.width, size.height]);
    const [lineObj] = useState(() => new LineSegments2());

    useEffect(() => () => { geo.dispose(); mat.dispose(); }, [geo, mat]);

    useFrame(() => {
        if (!dirtyRef.current) return;
        const skeleton = skeletonRef.current;
        if (!skeleton) return;

        const posAttr = geo.attributes.instanceStart as InterleavedBufferAttribute;
        const colAttr = geo.attributes.instanceColorStart as InterleavedBufferAttribute;
        const pos = posAttr.data.array as Float32Array;
        const col = colAttr.data.array as Float32Array;

        for (let i = 0; i < connections.length; i++) {
            const [parent, child] = connections[i];
            const pi = nameToIndexRef.current.get(parent);
            const ci = nameToIndexRef.current.get(child);
            const base = i * 6;

            const pOk = pi !== undefined && Number.isFinite(skeleton.interleaved[pi * 3])
                && Number.isFinite(skeleton.interleaved[pi * 3 + 1]) && Number.isFinite(skeleton.interleaved[pi * 3 + 2]);
            const cOk = ci !== undefined && Number.isFinite(skeleton.interleaved[ci * 3])
                && Number.isFinite(skeleton.interleaved[ci * 3 + 1]) && Number.isFinite(skeleton.interleaved[ci * 3 + 2]);

            if (pOk && cOk) {
                const po = pi! * 3;
                const co = ci! * 3;
                pos[base]     = skeleton.interleaved[po];
                pos[base + 1] = skeleton.interleaved[po + 1];
                pos[base + 2] = skeleton.interleaved[po + 2];
                pos[base + 3] = skeleton.interleaved[co];
                pos[base + 4] = skeleton.interleaved[co + 1];
                pos[base + 5] = skeleton.interleaved[co + 2];
                const rgb = edgeColor(child);
                col[base]     = rgb[0]; col[base + 1] = rgb[1]; col[base + 2] = rgb[2];
                col[base + 3] = rgb[0]; col[base + 4] = rgb[1]; col[base + 5] = rgb[2];
            } else {
                for (let j = 0; j < 6; j++) { pos[base + j] = 1e5; col[base + j] = 0; }
            }
        }

        posAttr.needsUpdate = true;
        colAttr.needsUpdate = true;
        dirtyRef.current = false;
    });

    return (
        <primitive object={lineObj} frustumCulled={false}>
            <primitive object={geo} attach="geometry" />
            <primitive object={mat} attach="material" />
        </primitive>
    );
}
