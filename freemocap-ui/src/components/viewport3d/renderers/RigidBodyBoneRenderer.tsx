// RigidBodyBoneRenderer.tsx
//
// The rigid-body segment renderer: a single THREE.InstancedMesh of every tracked model's
// bone meshes, driven each frame by that model's SEGMENT_ORIGINS + ROTATIONS_WORLD.
// Identity quaternion == rest pose.
//
// It draws EVERY model in the frame, not "the" skeleton — a tracked person and a tracked
// charuco board share the one instanced mesh. Each model gets a contiguous block of
// instance slots, so a model's own row index (which is what indexes its channel data)
// stays model-local while the mesh slot is that row plus the model's block base. Conflating
// the two is how a second model would overwrite the first's bones.
//
// Name→slot resolution is built ONCE per model set; per-instance colors are set ONCE at
// build; the cross-section radius is a fixed parameter independent of segment length; every
// bone index resolves by its MODEL-DECLARED NAME. Because a model's segment order IS its
// channel row order, the name→row map doubles as the channel row index — the hot path reads
// rows by index, never by name lookup.
//
// The bone is oriented along its PRIMARY AXIS (origin→distal), then composed with the
// rest-frame orientation and the world quaternion.
//
// Design note (honest): this renderer consumes ROTATIONS_WORLD and CANNOT validate
// ROTATIONS_LOCAL — it renders world quaternions. The local-rotation trap
// (parent-relative quaternions) is the solver tests' job.

import { useCallback, useEffect, useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import {
    Color,
    InstancedMesh,
    Matrix4,
    MeshBasicMaterial,
    Object3D,
} from "three";
import { useKeypointsSource, useModelDefinitionsById } from "../KeypointsSourceContext";
import { registerPickingMesh, unregisterPickingMesh } from "./PickingRegistry";
import type { ResolvedModelFrame, SegmentLengthsFrame } from "@/services/server/transport/frame-types";
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
 *       has one once the model is measured, including the ones nothing can currently see
 *       (those are sized by the fitted scale);
 *    2. the model's proportion times the fitted scale, if the lengths channel is absent
 *       but a scale is known;
 *    3. DEFAULT_SEGMENT_LENGTH, which means this model has no measured size at all.
 */
let warnedAboutMissingSize = false;

export function resolveBoneLengthMm(
    table: BoneInstanceTable,
    liveLengths: SegmentLengthsFrame | null,
    name: string,
    row: number,
): number {
    const fitted = liveLengths?.data[row];
    if (fitted !== undefined && Number.isFinite(fitted) && fitted > 0) return fitted;

    const proportion = table.byNameLengthProportion.get(name);
    const fittedScaleMm = liveLengths?.fittedScaleMm;
    if (proportion !== undefined && proportion > 0 && fittedScaleMm != null && fittedScaleMm > 0) {
        return proportion * fittedScaleMm;
    }

    // Falling through means the bones are about to be drawn a millimetre long, which reads
    // as "the renderer is broken" rather than "nothing has told me how big this thing is".
    // Say so once — a silent version of this cost an afternoon.
    if (!warnedAboutMissingSize) {
        warnedAboutMissingSize = true;
        console.warn(
            "[RigidBodyBoneRenderer] no size for this model: neither a fitted SEGMENT_LENGTHS " +
            "row nor a fitted scale reached this renderer, so bones are drawn at " +
            `${DEFAULT_SEGMENT_LENGTH}mm and will look invisible. The model is dimensionless — ` +
            "check that model frames are being forwarded to the viewport worker.",
        );
    }
    return DEFAULT_SEGMENT_LENGTH;
}

// Per-region transverse cross-section radius (mm), resolved at model time and stored on
// the table (face < hand < body). The radius is independent of a segment's LENGTH — a
// 1 mm and a 500 mm bone in the same region match.

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

/** One model's bone table plus where its block of instance slots starts. */
interface ModelBoneBlock {
    modelId: string;
    table: BoneInstanceTable;
    baseSlot: number;
}

/** Identity of the MODEL SET — what a rebuild depends on. */
function modelSetSignature(models: ResolvedModelFrame[]): string {
    return models.map((m) => m.modelId).join("|");
}

export function RigidBodyBoneRenderer() {
    const { subscribeToModelFrames } = useKeypointsSource();
    const definitionsById = useModelDefinitionsById();
    const meshRef = useRef<InstancedMesh>(null);
    const idxToNameRef = useRef<Map<number, string>>(new Map());

    const modelFramesRef = useRef<ResolvedModelFrame[] | null>(null);
    const dirtyRef = useRef(false);

    const blocksRef = useRef<ModelBoneBlock[]>([]);
    const signatureRef = useRef<string>("");
    const blocksAppliedRef = useRef(false);

    const geometry = useMemo(() => createBoneMeshGeometry(), []);
    const material = useMemo(
        () => new MeshBasicMaterial({ color: "#ffffff" }),
        [],
    );

    useEffect(() => () => { geometry.dispose(); material.dispose(); }, [geometry, material]);

    const applyBlocks = useCallback(() => {
        const mesh = meshRef.current;
        if (!mesh || blocksAppliedRef.current) return;

        for (let i = 0; i < MAX_BONES; i++) {
            DUMMY.position.set(0, 0, 0);
            DUMMY.scale.set(0, 0, 0);
            DUMMY.updateMatrix();
            mesh.setMatrixAt(i, DUMMY.matrix);
            mesh.setColorAt(i, HIDDEN_COLOR);
        }
        if (mesh.instanceColor) {
            for (const block of blocksRef.current) {
                for (const inst of block.table.instances) {
                    mesh.setColorAt(block.baseSlot + inst.instanceIdx, SIDE_COLORS[inst.side]);
                }
            }
            mesh.instanceColor.needsUpdate = true;
        }
        mesh.instanceMatrix.needsUpdate = true;
        mesh.count = MAX_BONES;
        blocksAppliedRef.current = true;
    }, []);

    // Build one slot block per model, ONCE per model set.
    const rebuild = useCallback((models: ResolvedModelFrame[]) => {
        const blocks: ModelBoneBlock[] = [];
        idxToNameRef.current.clear();
        let nextSlot = 0;
        for (const entry of models) {
            const definition = definitionsById.current.get(entry.modelId);
            if (!definition) continue;
            const table = buildBoneInstances(definition);
            const segmentCount = definition.segments.length;
            if (nextSlot + segmentCount > MAX_BONES) {
                console.warn(
                    `[RigidBodyBoneRenderer] out of instance slots at model "${entry.modelId}": ` +
                    `${nextSlot + segmentCount} segments across ${models.length} models exceeds ` +
                    `${MAX_BONES}. Its bones will not draw.`,
                );
                break;
            }
            for (const inst of table.instances) {
                idxToNameRef.current.set(nextSlot + inst.instanceIdx, inst.name);
            }
            blocks.push({ modelId: entry.modelId, table, baseSlot: nextSlot });
            nextSlot += segmentCount;
        }
        blocksRef.current = blocks;
        blocksAppliedRef.current = false;
        applyBlocks();
    }, [applyBlocks, definitionsById]);

    useEffect(() => {
        return subscribeToModelFrames((models) => {
            modelFramesRef.current = models;
            const signature = `${modelSetSignature(models)}#${definitionsById.current.size}`;
            if (signature !== signatureRef.current) {
                signatureRef.current = signature;
                rebuild(models);
            }
            dirtyRef.current = true;
        });
    }, [subscribeToModelFrames, rebuild, definitionsById]);

    // The mesh ref is null on the first model arrival of a fresh mount, so the colors are
    // applied again once it exists.
    useEffect(() => {
        applyBlocks();
    }, [applyBlocks]);

    // Per-frame update: place + orient + scale each resolved instance by INDEX (a model's
    // segment order IS its channel row order, so no name lookup).
    useFrame(() => {
        const mesh = meshRef.current;
        const models = modelFramesRef.current;
        if (!mesh || !models || !dirtyRef.current || !blocksAppliedRef.current) return;

        const frameByModelId = new Map(models.map((m) => [m.modelId, m]));

        for (const block of blocksRef.current) {
            const entry = frameByModelId.get(block.modelId);
            const origins = entry?.segmentOrigins;
            const rotations = entry?.rotations;
            const liveLengths = entry?.segmentLengths ?? null;

            for (const [name, row] of block.table.nameToIndex) {
                const slot = block.baseSlot + row;
                let visible = false;

                if (origins && rotations) {
                    const o = row * 3;
                    const q = row * 4;
                    const ox = origins.data[o];
                    const oy = origins.data[o + 1];
                    const oz = origins.data[o + 2];
                    const qw = rotations.worldQuaternions[q];
                    const qx = rotations.worldQuaternions[q + 1];
                    const qy = rotations.worldQuaternions[q + 2];
                    const qz = rotations.worldQuaternions[q + 3];

                    const finiteOrigin =
                        Number.isFinite(ox) && Number.isFinite(oy) && Number.isFinite(oz);
                    const finiteQuat =
                        Number.isFinite(qw) && Number.isFinite(qx) &&
                        Number.isFinite(qy) && Number.isFinite(qz);

                    if (finiteOrigin && finiteQuat) {
                        const matrix = computeBoneMatrix(
                            [ox, oy, oz],
                            [qw, qx, qy, qz],
                            block.table.byNameRestOrientation.get(name)!,
                            block.table.byNamePrimaryAxis.get(name)!,
                            resolveBoneLengthMm(block.table, liveLengths, name, row),
                            block.table.byNameCrossSection.get(name) ?? 12,
                        );
                        if (matrix !== null) {
                            mesh.setMatrixAt(slot, _matrix4.fromArray(matrix));
                            visible = true;
                        }
                    }
                }

                if (!visible) {
                    DUMMY.position.set(0, 0, 0);
                    DUMMY.scale.set(0, 0, 0);
                    DUMMY.updateMatrix();
                    mesh.setMatrixAt(slot, DUMMY.matrix);
                }
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
