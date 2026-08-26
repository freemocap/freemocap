// RigidBodyBoneRenderer.tsx
//
// The rigid-body segment renderer: a single THREE.InstancedMesh of the
// standard-human bone meshes, driven every frame by:
//   SEGMENT_ORIGINS (via subscribeToSkeleton) + ROTATIONS_WORLD (via
//   subscribeToRotations). Identity quaternion == T-pose.
//
// Name→slot resolution is built ONCE at model time (D14); per-instance colors
// are set ONCE at build (D15); the cross-section radius is a fixed parameter
// independent of segment length (D6); every bone index resolves by its
// MODEL-DECLARED NAME (D5). Because the model's segment order IS the channel
// row order, the name→slot map doubles as the channel row index — the hot path
// reads rows by index, never by name lookup.
//
// The bone is oriented along its PRIMARY AXIS (origin→distal), then composed
// with the rest-frame orientation and the world quaternion.
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
} from "three";
import { useKeypointsSource, type KeypointsFrame } from "../KeypointsSourceContext";
import { registerPickingMesh, unregisterPickingMesh } from "./PickingRegistry";
import type { RotationsFrame, SegmentLengthsFrame } from "@/services/server/transport/frame-types";
import type { ModelDefinition } from "@/services/server/transport/message-contract";
import { createBoneMeshGeometry } from "./RigidBodyBoneGeometry";
import {
    BONE_SIDE_COLORS,
    DEFAULT_SEGMENT_LENGTH,
    buildBoneInstances,
    computeBoneMatrix,
    type BoneInstanceTable,
} from "./RigidBodyBoneInstances";

const MAX_BONES = 256;

/** How long to draw one bone, in millimetres.
 *
 *  The model is dimensionless, so a length is always something the FIT supplies. In order
 *  of preference:
 *    1. the segment's own fitted length from this frame's SEGMENT_LENGTHS — every segment
 *       has one once the subject is measured, including the ones nothing can currently
 *       see (those are sized by the fitted body height);
 *    2. the model's proportion times the fitted body height, if the lengths channel is
 *       absent but a height is known;
 *    3. DEFAULT_SEGMENT_LENGTH, which means the subject has no measured size at all.
 */
let warnedAboutMissingSize = false;

export function resolveBoneLengthMm(
    table: BoneInstanceTable,
    liveLengths: SegmentLengthsFrame | null,
    name: string,
    slot: number,
): number {
    const fitted = liveLengths?.data[slot];
    if (fitted !== undefined && Number.isFinite(fitted) && fitted > 0) return fitted;

    const proportion = table.byNameLengthProportion.get(name);
    const bodyHeightMm = liveLengths?.bodyHeightMm;
    if (proportion !== undefined && proportion > 0 && bodyHeightMm != null && bodyHeightMm > 0) {
        return proportion * bodyHeightMm;
    }

    // Falling through means the bones are about to be drawn a millimetre long, which reads
    // as "the renderer is broken" rather than "nothing has told me how big this person is".
    // Say so once — a silent version of this cost an afternoon.
    if (!warnedAboutMissingSize) {
        warnedAboutMissingSize = true;
        console.warn(
            "[RigidBodyBoneRenderer] no size for the subject: neither a fitted SEGMENT_LENGTHS " +
            "row nor a body height reached this renderer, so bones are drawn at " +
            `${DEFAULT_SEGMENT_LENGTH}mm and will look invisible. The model is dimensionless — ` +
            "check that segment lengths are being forwarded to the viewport worker.",
        );
    }
    return DEFAULT_SEGMENT_LENGTH;
}

// Per-region transverse cross-section radius (mm), resolved at model time and
// stored on the table (face < hand < body). D6: the radius is independent of a
// segment's LENGTH — a 1 mm and a 500 mm bone in the same region match.

// Scratch (zero per-frame allocation).
const DUMMY = new Object3D();
const _matrix4 = new Matrix4();

const BONE_COLOR_DIM = 0.7;
// Derived from the shared table rather than re-listed, so a new side gets its bone color
// for free instead of silently falling back to whatever `Record` lookup returns.
const SIDE_COLORS = Object.fromEntries(
    Object.entries(BONE_SIDE_COLORS).map(([side, rgb]) => [
        side,
        new Color(...(rgb as [number, number, number])).multiplyScalar(BONE_COLOR_DIM),
    ]),
) as Record<string, Color>;
const HIDDEN_COLOR = new Color("#000000");

export function RigidBodyBoneRenderer() {
    const { subscribeToSkeleton, subscribeToRotations, subscribeToModels, getModels, getLatestSegmentLengths } =
        useKeypointsSource();
    const meshRef = useRef<InstancedMesh>(null);
    const idxToNameRef = useRef<Map<number, string>>(new Map());

    const skeletonRef = useRef<KeypointsFrame | null>(null);
    const rotationsRef = useRef<RotationsFrame | null>(null);
    const dirtyRef = useRef(false);

    // Model-time name→slot table (D5/D14); rebuilt once on model arrival.
    const tableRef = useRef<BoneInstanceTable | null>(null);
    const tableAppliedRef = useRef(false);

    const geometry = useMemo(() => createBoneMeshGeometry(), []);
    const material = useMemo(
        () => new MeshBasicMaterial({ color: "#ffffff" }),
        [],
    );

    useEffect(() => () => { geometry.dispose(); material.dispose(); }, [geometry, material]);

    const applyTable = useCallback(() => {
        const mesh = meshRef.current;
        const table = tableRef.current;
        if (!mesh || !table || tableAppliedRef.current) return;

        for (let i = 0; i < MAX_BONES; i++) {
            DUMMY.position.set(0, 0, 0);
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
    }, []);

    // Build the name→slot table ONCE per model arrival (D14).
    const rebuild = useCallback((model: ModelDefinition) => {
        tableRef.current = buildBoneInstances(model);
        idxToNameRef.current.clear();
        for (const inst of tableRef.current.instances) {
            idxToNameRef.current.set(inst.instanceIdx, inst.name);
        }
        tableAppliedRef.current = false;
        applyTable();
    }, [applyTable]);

    // Initial model (if already held) + every subsequent model arrival.
    useEffect(() => {
        const unsub = subscribeToModels ? subscribeToModels((models) => {
            if (models.length > 0) rebuild(models[0]);
        }) : () => {};
        const existing = getModels?.();
        if (existing && existing.length > 0) rebuild(existing[0]);
        return unsub;
    }, [getModels, subscribeToModels, rebuild]);

    useEffect(() => {
        applyTable();
    }, [applyTable, getModels, subscribeToModels]);

    // Subscribe segment origins (SEGMENT_ORIGINS, 3-interleaved xyz, model order).
    useEffect(() => {
        return subscribeToSkeleton((frame) => {
            skeletonRef.current = frame;
            dirtyRef.current = true;
        });
    }, [subscribeToSkeleton]);

    // Subscribe world rotations (ROTATIONS_WORLD, 4-interleaved wxyz, model order).
    useEffect(() => {
        if (!subscribeToRotations) return;
        return subscribeToRotations((frame) => {
            rotationsRef.current = frame;
            dirtyRef.current = true;
        });
    }, [subscribeToRotations]);

    // Per-frame update: place + orient + scale each resolved instance by INDEX
    // (the model segment order IS the channel row order, so no name lookup).
    useFrame(() => {
        const mesh = meshRef.current;
        const table = tableRef.current;

        if (!mesh || !table || !dirtyRef.current || !tableAppliedRef.current) return;

        const skeleton = skeletonRef.current;
        const rotations = rotationsRef.current;
        if (!skeleton || !rotations) return;
        const liveLengths = getLatestSegmentLengths ? getLatestSegmentLengths() : null;

        for (const [name, slot] of table.nameToIndex) {
            const o = slot * 3;
            const q = slot * 4;
            const ox = skeleton.interleaved[o];
            const oy = skeleton.interleaved[o + 1];
            const oz = skeleton.interleaved[o + 2];
            const qw = rotations.worldQuaternions[q];
            const qx = rotations.worldQuaternions[q + 1];
            const qy = rotations.worldQuaternions[q + 2];
            const qz = rotations.worldQuaternions[q + 3];
            let visible = false;

            const finiteOrigin = Number.isFinite(ox) && Number.isFinite(oy) && Number.isFinite(oz);
            const finiteQuat =
                Number.isFinite(qw) && Number.isFinite(qx) && Number.isFinite(qy) && Number.isFinite(qz);

            if (finiteOrigin && finiteQuat) {
                const matrix = computeBoneMatrix(
                    [ox, oy, oz],
                    [qw, qx, qy, qz],
                    table.byNameRestOrientation.get(name)!,
                    table.byNamePrimaryAxis.get(name)!,
                    resolveBoneLengthMm(table, liveLengths, name, slot),
                    table.byNameCrossSection.get(name) ?? 12,
                );
                if (matrix !== null) {
                    mesh.setMatrixAt(slot, _matrix4.fromArray(matrix));
                    visible = true;
                }
            }

            if (!visible) {
                DUMMY.position.set(0, 0, 0);
                DUMMY.scale.set(0, 0, 0);
                DUMMY.updateMatrix();
                mesh.setMatrixAt(slot, DUMMY.matrix);
            }
        }

        mesh.instanceMatrix.needsUpdate = true;
        dirtyRef.current = false;
    });

    // Register with the manual raycast picker (ViewportPicker).
    useEffect(() => {
        const mesh = meshRef.current;
        if (!mesh) return;
        registerPickingMesh(mesh, { kind: "segment", instanceIdToName: idxToNameRef.current });
        return () => unregisterPickingMesh(mesh);
    }, []);

    return (
        <instancedMesh
            ref={meshRef}
            args={[geometry, material, MAX_BONES]}
            frustumCulled={false}
        />
    );
}
