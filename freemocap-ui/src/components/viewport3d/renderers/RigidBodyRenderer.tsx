import { useEffect, useMemo, useRef } from "react";
import {
    CylinderGeometry,
    Group,
    InstancedMesh,
    MeshStandardMaterial,
    Object3D,
    Vector3,
} from "three";
import { useFrame } from "@react-three/fiber";
import { useServer } from "@/services";
import { RigidBodyPose } from "../helpers/viewport3d-types";
import { useViewportState } from "../scene/ViewportStateContext";
import { COLORS } from "../helpers/colors";

const MAX_BODIES = 128;
const DUMMY = new Object3D();
const FAR_AWAY = new Vector3(1e5, 1e5, 1e5);

/** Shaft radius for the main Z-axis cylinder. */
const SHAFT_RADIUS = 0.012;
/** Crossbar radius and length for X/Y axis indicators. */
const CROSSBAR_RADIUS = 0.006;
const CROSSBAR_LENGTH = 0.04;

/**
 * Renders rigid body segments as instanced cylinders along local Z,
 * with small crossbars at the origin showing X (red) and Y (green) axes.
 *
 * Uses 3 instanced meshes:
 *  - main shafts  (Z axis, bone color)
 *  - X crossbars  (red)
 *  - Y crossbars  (green)
 */
export function RigidBodyRenderer() {
    const { subscribeToRigidBodies } = useServer();
    const { statsRef } = useViewportState();

    const shaftRef = useRef<InstancedMesh>(null);
    const xBarRef = useRef<InstancedMesh>(null);
    const yBarRef = useRef<InstancedMesh>(null);

    const posesRef = useRef<Map<string, RigidBodyPose>>(new Map());
    const nameToIdx = useRef<Map<string, number>>(new Map());
    const nextIdx = useRef(0);
    const dirtyRef = useRef(false);

    // Shaft geometry: unit cylinder along +Z, origin at bottom
    const shaftGeo = useMemo(() => {
        const g = new CylinderGeometry(1, 1, 1, 6, 1);
        g.rotateX(Math.PI / 2);  // Y → Z
        g.translate(0, 0, 0.5);  // origin at bottom
        return g;
    }, []);

    // Crossbar geometry: short cylinder along +X (will be rotated for Y)
    const crossbarGeo = useMemo(() => {
        const g = new CylinderGeometry(1, 1, 1, 4, 1);
        // leave along Y — we'll orient per-instance
        return g;
    }, []);

    const shaftMat = useMemo(() => new MeshStandardMaterial({
        color: "#ffffff", roughness: 0.5, metalness: 0.2, transparent: true, opacity: 0.7,
    }), []);
    const xMat = useMemo(() => new MeshStandardMaterial({ color: COLORS.rigidBodyX }), []);
    const yMat = useMemo(() => new MeshStandardMaterial({ color: COLORS.rigidBodyY }), []);

    useEffect(() => {
        return subscribeToRigidBodies((newPoses: Map<string, RigidBodyPose>) => {
            posesRef.current = newPoses;
            dirtyRef.current = true;
            for (const key of newPoses.keys()) {
                if (!nameToIdx.current.has(key) && nextIdx.current < MAX_BODIES) {
                    nameToIdx.current.set(key, nextIdx.current++);
                }
            }
        });
    }, [subscribeToRigidBodies]);

    // Init all hidden
    useEffect(() => {
        for (const mesh of [shaftRef.current, xBarRef.current, yBarRef.current]) {
            if (!mesh) continue;
            for (let i = 0; i < MAX_BODIES; i++) {
                DUMMY.position.copy(FAR_AWAY);
                DUMMY.scale.set(0, 0, 0);
                DUMMY.updateMatrix();
                mesh.setMatrixAt(i, DUMMY.matrix);
                if (mesh === shaftRef.current) mesh.setColorAt(i, COLORS.hidden);
            }
            mesh.instanceMatrix.needsUpdate = true;
            if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
            mesh.count = MAX_BODIES;
        }
    }, []);

    useFrame(() => {
        const shaft = shaftRef.current;
        const xBar = xBarRef.current;
        const yBar = yBarRef.current;
        if (!shaft || !xBar || !yBar || !dirtyRef.current) return;

        const poses = posesRef.current;
        let count = 0;

        for (const [key, idx] of nameToIdx.current) {
            const pose = poses.get(key);

            if (pose) {
                const [px, py, pz] = pose.position;
                const [qw, qx, qy, qz] = pose.orientation;
                const [sx, sy, sz] = pose.scale;

                // Main shaft along local Z
                DUMMY.position.set(px, py, pz);
                DUMMY.quaternion.set(qx, qy, qz, qw);
                DUMMY.scale.set(SHAFT_RADIUS, SHAFT_RADIUS, sz);
                DUMMY.updateMatrix();
                shaft.setMatrixAt(idx, DUMMY.matrix);
                shaft.setColorAt(idx, COLORS.rigidBody);

                // X crossbar: rotate 90° around Z from the bone frame, scale along local Y
                DUMMY.scale.set(CROSSBAR_RADIUS, CROSSBAR_LENGTH, CROSSBAR_RADIUS);
                DUMMY.updateMatrix();
                // We need to apply an additional 90° rotation around Z for the X bar
                // Simpler: just set scale to put length along X
                DUMMY.scale.set(CROSSBAR_LENGTH, CROSSBAR_RADIUS, CROSSBAR_RADIUS);
                DUMMY.updateMatrix();
                xBar.setMatrixAt(idx, DUMMY.matrix);

                // Y crossbar
                DUMMY.scale.set(CROSSBAR_RADIUS, CROSSBAR_LENGTH, CROSSBAR_RADIUS);
                DUMMY.updateMatrix();
                yBar.setMatrixAt(idx, DUMMY.matrix);

                count++;
            } else {
                DUMMY.position.copy(FAR_AWAY);
                DUMMY.scale.set(0, 0, 0);
                DUMMY.updateMatrix();
                shaft.setMatrixAt(idx, DUMMY.matrix);
                shaft.setColorAt(idx, COLORS.hidden);
                xBar.setMatrixAt(idx, DUMMY.matrix);
                yBar.setMatrixAt(idx, DUMMY.matrix);
            }
        }

        for (const mesh of [shaft, xBar, yBar]) {
            mesh.instanceMatrix.needsUpdate = true;
            if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
        }
        dirtyRef.current = false;
        statsRef.current.rigidBodies = count;
    });

    return (
        <>
            <instancedMesh ref={shaftRef} args={[shaftGeo, shaftMat, MAX_BODIES]} frustumCulled={false} />
            <instancedMesh ref={xBarRef} args={[crossbarGeo, xMat, MAX_BODIES]} frustumCulled={false} />
            <instancedMesh ref={yBarRef} args={[crossbarGeo, yMat, MAX_BODIES]} frustumCulled={false} />
        </>
    );
}
