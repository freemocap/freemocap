import {useEffect, useMemo, useRef} from "react";
import {Color, CylinderGeometry, InstancedMesh, MeshStandardMaterial, Object3D, Vector3,} from "three";
import {useFrame} from "@react-three/fiber";
import {useServer} from "@/services";
import {RigidBodyPose} from "@/components/viewport3d/helpers/viewport3d-types";
import {Z_OFFSET} from "@/components/viewport3d/skeleton-config";
import {SKELETON_COLORS} from "@/components/viewport3d/skeleton-colors";

/** Maximum bone segments the instanced mesh can hold. */
const MAX_RIGID_BODIES = 64;

/** Cylinder cross-section radius in meters. */
const BODY_RADIUS = 0.025;
const HAND_RADIUS = 0.008;

const DUMMY = new Object3D();
const FAR_AWAY = new Vector3(10000, 10000, 10000);

function getRigidBodyColor(boneKey: string): Color {
    if (boneKey.includes("left_hand"))  return SKELETON_COLORS.leftHand;
    if (boneKey.includes("right_hand")) return SKELETON_COLORS.rightHand;
    if (boneKey.includes("left"))       return SKELETON_COLORS.left;
    if (boneKey.includes("right"))      return SKELETON_COLORS.right;
    return SKELETON_COLORS.center;
}

function getRigidBodyRadius(boneKey: string): number {
    if (boneKey.includes("hand")) return HAND_RADIUS;
    return BODY_RADIUS;
}

/**
 * Renders rigid body bone segments as instanced cylinders.
 *
 * Subscribes directly to the server's rigid-body stream and updates
 * only dirty instances each frame to minimize GPU uploads. Follows the
 * same mutable-ref + useFrame pattern as SkeletonRenderer.
 */
export function RigidBodyRenderer() {
    const { subscribeToRigidBodies } = useServer();
    const instancedMeshRef = useRef<InstancedMesh>(null);

    // Mutable refs for frame-loop access without React re-renders
    const rigidBodiesRef = useRef<Map<string, RigidBodyPose>>(new Map());
    const boneKeyToIndexRef = useRef<Map<string, number>>(new Map());
    const indexToBoneKeyRef = useRef<Map<number, string>>(new Map());
    const nextIndexRef = useRef<number>(0);
    const dirtyRef = useRef<boolean>(false);

    // Unit cylinder centered at origin along +Y, then:
    //  - rotated so axis is +Z
    //  - translated so bottom face is at origin (extends 0 → +1 along Z)
    // This way scale.z = bone length places the cylinder from parent → child.
    const cylinderGeometry = useMemo(() => {
        const geo = new CylinderGeometry(1, 1, 1, 8, 1);
        geo.rotateX(Math.PI / 2);   // +Y axis → +Z axis
        geo.translate(0, 0, 0.5);   // origin at bottom face (parent joint)
        return geo;
    }, []);

    // Semi-transparent material — per-instance color tints it
    const cylinderMaterial = useMemo(() => new MeshStandardMaterial({
        color: '#ffffff',
        roughness: 0.45,
        metalness: 0.3,
        transparent: true,
        opacity: 0.6,
    }), []);

    // Assign stable instance index for a bone key
    const assignIndex = (boneKey: string): number => {
        if (nextIndexRef.current >= MAX_RIGID_BODIES) {
            throw new Error(`Maximum rigid bodies (${MAX_RIGID_BODIES}) exceeded for bone "${boneKey}"`);
        }
        const index = nextIndexRef.current++;
        boneKeyToIndexRef.current.set(boneKey, index);
        indexToBoneKeyRef.current.set(index, boneKey);
        return index;
    };

    // Subscribe to rigid body stream
    useEffect(() => {
        const unsubscribe = subscribeToRigidBodies((newPoses: Map<string, RigidBodyPose>) => {
            rigidBodiesRef.current = newPoses;
            dirtyRef.current = true;

            // Assign indices for any new bones
            for (const boneKey of newPoses.keys()) {
                if (!boneKeyToIndexRef.current.has(boneKey)) {
                    assignIndex(boneKey);
                }
            }
        });

        return unsubscribe;
    }, [subscribeToRigidBodies]);

    // Initialize all instances as hidden
    useEffect(() => {
        if (!instancedMeshRef.current) return;
        const mesh = instancedMeshRef.current;

        for (let i = 0; i < MAX_RIGID_BODIES; i++) {
            DUMMY.position.copy(FAR_AWAY);
            DUMMY.scale.set(0, 0, 0);
            DUMMY.updateMatrix();
            mesh.setMatrixAt(i, DUMMY.matrix);
            mesh.setColorAt(i, SKELETON_COLORS.hidden);
        }
        mesh.instanceMatrix.needsUpdate = true;
        if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
        mesh.count = MAX_RIGID_BODIES;
    }, []);

    // Per-frame update: apply transforms for all assigned bones
    useFrame(() => {
        if (!instancedMeshRef.current || !dirtyRef.current) return;
        const mesh = instancedMeshRef.current;
        const poses = rigidBodiesRef.current;

        for (let i = 0; i < nextIndexRef.current; i++) {
            const boneKey = indexToBoneKeyRef.current.get(i);
            if (!boneKey) continue;

            const pose = poses.get(boneKey);
            if (pose) {
                const [px, py, pz] = pose.position;
                const [qw, qx, qy, qz] = pose.orientation;
                const radius = getRigidBodyRadius(boneKey);

                DUMMY.position.set(px, py, pz + Z_OFFSET);

                // Bone quaternion (local +Z = bone direction).
                // Three.js Quaternion constructor: (x, y, z, w).
                // The geometry is already pre-rotated so its axis is +Z,
                // so we apply the bone quaternion directly.
                DUMMY.quaternion.set(qx, qy, qz, qw);

                // Scale: x/y = radius, z = bone length
                DUMMY.scale.set(radius, radius, pose.length);

                mesh.setColorAt(i, getRigidBodyColor(boneKey));
            } else {
                DUMMY.position.copy(FAR_AWAY);
                DUMMY.scale.set(0, 0, 0);
                mesh.setColorAt(i, SKELETON_COLORS.hidden);
            }

            DUMMY.updateMatrix();
            mesh.setMatrixAt(i, DUMMY.matrix);
        }

        mesh.instanceMatrix.needsUpdate = true;
        if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
        dirtyRef.current = false;
    });

    return (
        <instancedMesh
            ref={instancedMeshRef}
            args={[cylinderGeometry, cylinderMaterial, MAX_RIGID_BODIES]}
            frustumCulled={false}
        />
    );
}
