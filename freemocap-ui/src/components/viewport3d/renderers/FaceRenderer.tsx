import { useEffect, useMemo, useRef } from "react";
import {
    BufferAttribute,
    BufferGeometry,
    LineBasicMaterial,
    LineSegments,
    Points,
    PointsMaterial,
} from "three";
import { useFrame, useThree } from "@react-three/fiber";
import { Point3d } from "../helpers/viewport3d-types";
import { useViewportState } from "../scene/ViewportStateContext";
import { COLORS } from "../helpers/colors";
import {FACE_CONTOUR_GROUPS} from "@/components/viewport3d/helpers/face-contours";
import { useKeypointsSource } from "../KeypointsSourceContext";

const MAX_FACE_POINTS = 512;
const DOT_SIZE = 2; // PointsMaterial sizeAttenuation=false → pixels

/**
 * Renders face mesh as small dots (THREE.Points) + contour line segments.
 * THREE.Points avoids per-instance matrix work of InstancedMesh — just writes
 * x/y/z directly into a Float32Array, which is a 10-20x speedup for 468 points.
 */
export function FaceRenderer() {
    const { subscribeToKeypointsRaw } = useKeypointsSource();
    const { statsRef } = useViewportState();
    const { invalidate } = useThree();

    const dotsRef = useRef<Points>(null);
    const linesRef = useRef<LineSegments>(null);

    const pointsRef = useRef<Map<string, Point3d>>(new Map());
    const nameToIdx = useRef<Map<string, number>>(new Map());
    const nextIdx = useRef(0);
    const dirtyRef = useRef(false);

    const dotGeo = useMemo(() => {
        const g = new BufferGeometry();
        g.setAttribute("position", new BufferAttribute(new Float32Array(MAX_FACE_POINTS * 3).fill(1e5), 3));
        return g;
    }, []);

    const dotMat = useMemo(() => new PointsMaterial({
        color: COLORS.face,
        size: DOT_SIZE,
        sizeAttenuation: false,
    }), []);

    const lineMat = useMemo(() => new LineBasicMaterial({
        color: COLORS.face,
        transparent: true,
        opacity: 0.7,
    }), []);

    const lineGeo = useMemo(() => {
        const g = new BufferGeometry();
        const n = FACE_CONTOUR_GROUPS.reduce((acc, g) => acc + g.connections.length, 0);
        const pos = new Float32Array(n * 6).fill(1e5);
        g.setAttribute("position", new BufferAttribute(pos, 3));
        return g;
    }, []);

    useEffect(() => () => {
        dotGeo.dispose();
        dotMat.dispose();
        lineMat.dispose();
        lineGeo.dispose();
    }, [dotGeo, dotMat, lineMat, lineGeo]);

    useEffect(() => {
        return subscribeToKeypointsRaw((allPts: Record<string, Point3d>) => {
            const face = pointsRef.current;
            face.clear();
            for (const [name, pt] of Object.entries(allPts)) {
                if (name.startsWith("face.")) face.set(name, pt);
            }
            dirtyRef.current = true;

            for (const name of face.keys()) {
                if (!nameToIdx.current.has(name) && nextIdx.current < MAX_FACE_POINTS) {
                    nameToIdx.current.set(name, nextIdx.current++);
                }
            }

            invalidate();
        });
    }, [subscribeToKeypointsRaw, invalidate]);

    useFrame(() => {
        if (!dirtyRef.current) return;
        const t0 = performance.now();

        const pts = pointsRef.current;
        const dotPositions = dotGeo.attributes.position.array as Float32Array;
        let count = 0;

        for (const [name, idx] of nameToIdx.current) {
            const pt = pts.get(name);
            const base = idx * 3;
            if (pt) {
                dotPositions[base]     = pt.x;
                dotPositions[base + 1] = pt.y;
                dotPositions[base + 2] = pt.z;
                count++;
            } else {
                dotPositions[base] = dotPositions[base + 1] = dotPositions[base + 2] = 1e5;
            }
        }
        dotGeo.attributes.position.needsUpdate = true;
        dotGeo.setDrawRange(0, nextIdx.current);

        // Update line segments
        const linePositions = lineGeo.attributes.position.array as Float32Array;
        let i = 0;
        for (const group of FACE_CONTOUR_GROUPS) {
            for (const [ai, bi] of group.connections) {
                const a = pts.get(`${group.prefix}_${ai}`);
                const b = pts.get(`${group.prefix}_${bi}`);
                const base = i * 6;
                if (a && b) {
                    linePositions[base] = a.x; linePositions[base+1] = a.y; linePositions[base+2] = a.z;
                    linePositions[base+3] = b.x; linePositions[base+4] = b.y; linePositions[base+5] = b.z;
                } else {
                    for (let j = 0; j < 6; j++) linePositions[base + j] = 1e5;
                }
                i++;
            }
        }
        lineGeo.attributes.position.needsUpdate = true;

        dirtyRef.current = false;
        statsRef.current.facePoints = count;
        const elapsed = performance.now() - t0;
        if (elapsed > 8) console.warn(`FaceRenderer useFrame: ${elapsed.toFixed(1)}ms`);
    });

    return (
        <>
            <points ref={dotsRef} geometry={dotGeo} material={dotMat} frustumCulled={false} />
            <lineSegments ref={linesRef} geometry={lineGeo} material={lineMat} frustumCulled={false} />
        </>
    );
}
