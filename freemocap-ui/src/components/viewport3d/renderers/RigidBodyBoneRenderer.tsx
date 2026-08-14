// RigidBodyBoneRenderer.tsx
//
// F4 — the rigid-body segment renderer: a single THREE.InstancedMesh of the
// canonical bone meshes, driven every frame by:
//   SEGMENT_ORIGINS (via subscribeToSkeleton) + ROTATIONS_WORLD (via
//   subscribeToRotations). Identity quaternion == T-pose.
//
// Name→slot resolution is built ONCE at schema time (D14); per-instance colors
// are set ONCE at build (D15); the cross-section radius is a fixed parameter
// independent of long-axis length (D6); every bone index resolves by its
// SCHEMA-DECLARED NAME (D5).
//
// Design note (honest, per doc 11): this renderer consumes ROTATIONS_WORLD and
// CANNOT validate ROTATIONS_LOCAL — it renders world quaternions. The
// local-rotation trap (parent-relative quaternions) is the solver tests' job.

import { useCallback, useEffect, useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import {
    Color,
    InstancedMesh,
    Matrix4,
    MeshBasicMaterial,
    Object3D,
    Vector3,
} from "three";
import { useKeypointsSource, type KeypointsFrame } from "../KeypointsSourceContext";
import type { RotationsFrame, StreamSchema } from "@/services/server/transport/types";
import { createBoneMeshGeometry } from "./RigidBodyBoneGeometry";
import {
    BONE_SIDE_COLORS,
    buildBoneInstances,
    computeBoneMatrix,
    type BoneInstanceTable,
} from "./RigidBodyBoneInstances";

const MAX_BONES = 256;
const FAR_AWAY = new Vector3(1e5, 1e5, 1e5);

// Fixed transverse cross-section (world units). D6: a 1 mm segment renders the
// SAME radius as a 500 mm one — long-axis `length` only scales the Z span.
const BONE_CROSS_SECTION = 0.5;

// Scratch (zero per-frame allocation).
const DUMMY = new Object3D();
const _matrix4 = new Matrix4();

// Pre-built side colors (D15: applied once at schema time).
const SIDE_COLORS: Record<string, Color> = {
    left: new Color(...BONE_SIDE_COLORS.left),
    right: new Color(...BONE_SIDE_COLORS.right),
    center: new Color(...BONE_SIDE_COLORS.center),
};
const HIDDEN_COLOR = new Color("#000000");

export function RigidBodyBoneRenderer() {
    const { subscribeToSkeleton, subscribeToRotations, getStreamSchema, subscribeToSchema } =
        useKeypointsSource();

    const meshRef = useRef<InstancedMesh>(null);

    // Latest-frame refs (the hot path reads these, never allocates).
    const skeletonRef = useRef<KeypointsFrame | null>(null);
    const rotationsRef = useRef<RotationsFrame | null>(null);
    const dirtyRef = useRef(false);

    // Schema-time name→slot table (D5/D14); rebuilt once on schema arrival.
    const tableRef = useRef<BoneInstanceTable | null>(null);
    const tableAppliedRef = useRef(false);

    const geometry = useMemo(() => createBoneMeshGeometry(), []);
    const material = useMemo(
        () => new MeshBasicMaterial({ vertexColors: false, color: "#ffffff" }),
        [],
    );

    useEffect(() => () => { geometry.dispose(); material.dispose(); }, [geometry, material]);

    // Build the name→slot table ONCE per schema arrival (D14).
    const rebuild = useCallback((schema: StreamSchema) => {
        tableRef.current = buildBoneInstances(schema);
        tableAppliedRef.current = false; // per-instance colors re-applied in the init effect
    }, []);

    // Initial schema (if already registered) + every subsequent schema arrival.
    useEffect(() => {
        const existing = getStreamSchema?.();
        if (existing) rebuild(existing);
        const unsub = subscribeToSchema ? subscribeToSchema(rebuild) : () => {};
        return unsub;
    }, [getStreamSchema, subscribeToSchema, rebuild]);

    // Hide all + set per-instance colors ONCE per table (D15).
    useEffect(() => {
        const mesh = meshRef.current;
        const table = tableRef.current;
        if (!mesh || !table || tableAppliedRef.current) return;

        for (let i = 0; i < MAX_BONES; i++) {
            DUMMY.position.copy(FAR_AWAY);
            DUMMY.scale.set(0, 0, 0);
            DUMMY.updateMatrix();
            mesh.setMatrixAt(i, DUMMY.matrix);
            mesh.setColorAt(i, HIDDEN_COLOR);
        }
        if (mesh.instanceColor) {
            for (const inst of table.instances) {
                mesh.setColorAt(inst.instanceIdx, SIDE_COLORS[inst.side]);
            }
            mesh.instanceColor.needsUpdate = true;
        }
        mesh.instanceMatrix.needsUpdate = true;
        mesh.count = MAX_BONES;
        tableAppliedRef.current = true;
    }, [tableRef]);

    // Subscribe segment origins (SEGMENT_ORIGINS, 3-interleaved xyz).
    useEffect(() => {
        return subscribeToSkeleton((frame) => {
            skeletonRef.current = frame;
            dirtyRef.current = true;
        });
    }, [subscribeToSkeleton]);

    // Subscribe world rotations (ROTATIONS_WORLD).
    useEffect(() => {
        if (!subscribeToRotations) return;
        return subscribeToRotations((frame) => {
            rotationsRef.current = frame;
            dirtyRef.current = true;
        });
    }, [subscribeToRotations]);

    // Per-frame update: place + orient + scale each resolved instance.
    useFrame(() => {
        const mesh = meshRef.current;
        const table = tableRef.current;
        if (!mesh || !table || !dirtyRef.current || !tableAppliedRef.current) return;

        const skeleton = skeletonRef.current;
        const rotations = rotationsRef.current;
        if (!skeleton || !rotations) return;

        for (const [name, slot] of table.nameToIndex) {
            const segIdx = skeleton.pointNames.indexOf(name);
            const qIdx = rotations.boneNames.indexOf(name);
            let visible = false;

            if (segIdx !== -1 && qIdx !== -1) {
                const o = segIdx * 3;
                const ox = skeleton.interleaved[o];
                const oy = skeleton.interleaved[o + 1];
                const oz = skeleton.interleaved[o + 2];

                const q = qIdx * 4;
                const qw = rotations.worldQuaternions[q];
                const qx = rotations.worldQuaternions[q + 1];
                const qy = rotations.worldQuaternions[q + 2];
                const qz = rotations.worldQuaternions[q + 3];

                const finiteOrigin =
                    Number.isFinite(ox) && Number.isFinite(oy) && Number.isFinite(oz);
                const finiteQuat =
                    Number.isFinite(qw) && Number.isFinite(qx) && Number.isFinite(qy) && Number.isFinite(qz);

                if (finiteOrigin && finiteQuat) {
                    // The long axis is scaled by the segment's rest length
                    // (resolved once at schema time, doc 11 F4 Step 3), not a
                    // fixed unit span. D6: the transverse cross-section stays a
                    // fixed parameter, independent of length.
                    const matrix = computeBoneMatrix(
                        [ox, oy, oz],
                        [qw, qx, qy, qz],
                        table.byNameLength.get(name) ?? 1.0,
                        BONE_CROSS_SECTION,
                    );
                    if (matrix !== null) {
                        mesh.setMatrixAt(slot, _matrix4.fromArray(matrix));
                        visible = true;
                    }
                }
            }

            if (!visible) {
                DUMMY.position.copy(FAR_AWAY);
                DUMMY.scale.set(0, 0, 0);
                DUMMY.updateMatrix();
                mesh.setMatrixAt(slot, DUMMY.matrix);
            }
        }

        mesh.instanceMatrix.needsUpdate = true;
        dirtyRef.current = false;
    });

    return (
        <instancedMesh
            ref={meshRef}
            args={[geometry, material, MAX_BONES]}
            frustumCulled={false}
        />
    );
}
