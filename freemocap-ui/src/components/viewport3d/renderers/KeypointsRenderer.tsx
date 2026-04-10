import { useEffect, useMemo, useRef } from "react";
import {
    Color,
    InstancedMesh,
    MeshStandardMaterial,
    Object3D,
    SphereGeometry,
    Vector3,
} from "three";
import { useFrame } from "@react-three/fiber";
import { useServer } from "@/services";
import { Point3d } from "../helpers/viewport3d-types";
import { useViewportState } from "../scene/ViewportStateContext";
import { COLORS } from "../helpers/colors";

const MAX_POINTS = 1024;
const DUMMY = new Object3D();
const FAR_AWAY = new Vector3(1e5, 1e5, 1e5);

const RAW_RADIUS = 0.08;
const FILTERED_RADIUS = 0.12;

interface KeypointLayerProps {
    subscribeKey: "subscribeToKeypointsRaw" | "subscribeToKeypointsFiltered";
    color: Color;
    radius: number;
    statsKey: "keypointsRaw" | "keypointsFiltered";
}

function KeypointLayer({ subscribeKey, color, radius, statsKey }: KeypointLayerProps) {
    const server = useServer();
    const { statsRef } = useViewportState();
    const meshRef = useRef<InstancedMesh>(null);
    const pointsRef = useRef<Record<string, Point3d>>({});  // plain object, matches wire format
    const dirtyRef = useRef(false);
    const nameToIdx = useRef<Map<string, number>>(new Map());
    const nextIdx = useRef(0);

    const geo = useMemo(() => new SphereGeometry(100, 8, 6), []);
    const mat = useMemo(() => new MeshStandardMaterial({
        color: "#ffffff",
        roughness: 0.4,
        metalness: 0.3,
    }), []);

    useEffect(() => {
        const subscribeFn = server[subscribeKey];
        return subscribeFn((pts: Record<string, Point3d>) => {
            pointsRef.current = pts;
            dirtyRef.current = true;
            for (const name of Object.keys(pts)) {                  // was: pts.keys()
                if (!nameToIdx.current.has(name) && nextIdx.current < MAX_POINTS) {
                    nameToIdx.current.set(name, nextIdx.current++);
                }
            }
        });
    }, [server, subscribeKey]);

    useEffect(() => {
        const mesh = meshRef.current;
        if (!mesh) return;
        for (let i = 0; i < MAX_POINTS; i++) {
            DUMMY.position.copy(FAR_AWAY);
            DUMMY.scale.set(0, 0, 0);
            DUMMY.updateMatrix();
            mesh.setMatrixAt(i, DUMMY.matrix);
            mesh.setColorAt(i, COLORS.hidden);
        }
        mesh.instanceMatrix.needsUpdate = true;
        if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
        mesh.count = MAX_POINTS;
    }, []);

    useFrame(() => {
        const mesh = meshRef.current;
        if (!mesh || !dirtyRef.current) return;
        const pts = pointsRef.current;
        let count = 0;

        for (const [name, idx] of nameToIdx.current) {
            const pt = pts[name];                                    // was: pts.get(name)
            if (pt) {
                DUMMY.position.set(pt.x, pt.y, pt.z);
                DUMMY.scale.setScalar(radius);
                mesh.setColorAt(idx, color);
                count++;
            } else {
                // Not in this packet — hide it
                DUMMY.position.copy(FAR_AWAY);
                DUMMY.scale.set(0, 0, 0);
                mesh.setColorAt(idx, COLORS.hidden);
            }
            DUMMY.updateMatrix();
            mesh.setMatrixAt(idx, DUMMY.matrix);
        }

        mesh.instanceMatrix.needsUpdate = true;
        if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
        dirtyRef.current = false;
        statsRef.current[statsKey] = count;
    });

    return (
        <instancedMesh ref={meshRef} args={[geo, mat, MAX_POINTS]} frustumCulled={false} />
    );
}

export function KeypointsRenderer() {
    const { visibility } = useViewportState();

    return (
        <>
            {visibility.keypointsRaw && (
                <KeypointLayer
                    subscribeKey="subscribeToKeypointsRaw"
                    color={COLORS.raw}
                    radius={RAW_RADIUS}
                    statsKey="keypointsRaw"
                />
            )}
            {visibility.keypointsFiltered && (
                <KeypointLayer
                    subscribeKey="subscribeToKeypointsFiltered"
                    color={COLORS.filtered}
                    radius={FILTERED_RADIUS}
                    statsKey="keypointsFiltered"
                />
            )}
        </>
    );
}
