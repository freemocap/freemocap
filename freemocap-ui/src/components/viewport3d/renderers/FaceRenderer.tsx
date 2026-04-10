import { useEffect, useMemo, useRef } from "react";
import {
    BufferAttribute,
    BufferGeometry,
    LineBasicMaterial,
    LineSegments,
    InstancedMesh,
    MeshBasicMaterial,
    Object3D,
    SphereGeometry,
    Vector3,
} from "three";
import { useFrame } from "@react-three/fiber";
import { useServer } from "@/services";
import { Point3d } from "../helpers/viewport3d-types";
import { useViewportState } from "../scene/ViewportStateContext";
import { COLORS } from "../helpers/colors";
import {FACE_CONTOUR_GROUPS} from "@/components/viewport3d/helpers/face-contours";

const MAX_FACE_POINTS = 512;
const DOT_RADIUS = 0.015;
const DUMMY = new Object3D();
const FAR_AWAY = new Vector3(1e5, 1e5, 1e5);

/**
 * Renders face mesh as small dots + contour line segments.
 * Subscribes to raw keypoints and filters for face.* names.
 */
export function FaceRenderer() {
    const { subscribeToKeypointsRaw } = useServer();
    const { statsRef } = useViewportState();

    const dotsRef = useRef<InstancedMesh>(null);
    const linesRef = useRef<LineSegments>(null);

    const pointsRef = useRef<Map<string, Point3d>>(new Map());
    const nameToIdx = useRef<Map<string, number>>(new Map());
    const nextIdx = useRef(0);
    const dirtyRef = useRef(false);

    const dotGeo = useMemo(() => new SphereGeometry(1, 4, 3), []);
    const dotMat = useMemo(() => new MeshBasicMaterial({ color: COLORS.face }), []);

    const lineMat = useMemo(() => new LineBasicMaterial({
        color: COLORS.face,
        transparent: true,
        opacity: 0.7,
    }), []);

    const lineGeo = useMemo(() => {
        const g = new BufferGeometry();
        const n = FACE_CONTOUR_GROUPS.reduce((acc, g) => acc + g.connections.length, 0);
        const pos = new Float32Array(n * 3).fill(1e5);
        g.setAttribute("position", new BufferAttribute(pos, 3));
        return g;
    }, []);

    useEffect(() => {
        return subscribeToKeypointsRaw((allPts: Record<string, Point3d>) => {
            const face = new Map<string, Point3d>();
            for (const [name, pt] of Object.entries(allPts)) {
                if (name.startsWith("face.")) face.set(name, pt);
            }
            pointsRef.current = face;
            dirtyRef.current = true;

            for (const name of face.keys()) {
                if (!nameToIdx.current.has(name) && nextIdx.current < MAX_FACE_POINTS) {
                    nameToIdx.current.set(name, nextIdx.current++);
                }
            }
        });
    }, [subscribeToKeypointsRaw]);

    useEffect(() => {
        const mesh = dotsRef.current;
        if (!mesh) return;
        for (let i = 0; i < MAX_FACE_POINTS; i++) {
            DUMMY.position.copy(FAR_AWAY);
            DUMMY.scale.set(0, 0, 0);
            DUMMY.updateMatrix();
            mesh.setMatrixAt(i, DUMMY.matrix);
        }
        mesh.instanceMatrix.needsUpdate = true;
        mesh.count = MAX_FACE_POINTS;
    }, []);

    useFrame(() => {
        const dots = dotsRef.current;
        if (!dots || !dirtyRef.current) return;

        const pts = pointsRef.current;
        let count = 0;

        for (const [name, idx] of nameToIdx.current) {
            const pt = pts.get(name);
            if (pt) {
                DUMMY.position.set(pt.x, pt.y, pt.z);
                DUMMY.scale.setScalar(DOT_RADIUS);
                count++;
            } else {
                DUMMY.position.copy(FAR_AWAY);
                DUMMY.scale.set(0, 0, 0);
            }
            DUMMY.updateMatrix();
            dots.setMatrixAt(idx, DUMMY.matrix);
        }
        dots.instanceMatrix.needsUpdate = true;

        // Update line segments
        const positions = lineGeo.attributes.position.array as Float32Array;
        let i = 0;
        for (const group of FACE_CONTOUR_GROUPS) {
            for (const [ai, bi] of group.connections) {
                const a = pts.get(`${group.prefix}_${ai}`);
                const b = pts.get(`${group.prefix}_${bi}`);
                const base = i * 6;
                if (a && b) {
                    positions[base] = a.x; positions[base+1] = a.y; positions[base+2] = a.z;
                    positions[base+3] = b.x; positions[base+4] = b.y; positions[base+5] = b.z;
                } else {
                    for (let j = 0; j < 6; j++) positions[base + j] = 1e5;
                }
                i++;
            }
        }
        lineGeo.attributes.position.needsUpdate = true;

        dirtyRef.current = false;
        statsRef.current.facePoints = count;
    });

    return (
        <>
            <instancedMesh ref={dotsRef} args={[dotGeo, dotMat, MAX_FACE_POINTS]} frustumCulled={false} />
            <lineSegments ref={linesRef} geometry={lineGeo} material={lineMat} frustumCulled={false} />
        </>
    );
}
