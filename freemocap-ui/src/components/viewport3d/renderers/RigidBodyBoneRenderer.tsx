import { useEffect, useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { InstancedMesh, MeshBasicMaterial } from "three";
import { useKeypointsSource, useModelDefinitionsById } from "../KeypointsSourceContext";
import { registerPickingMesh, unregisterPickingMesh } from "./PickingRegistry";
import type { ResolvedModelFrame } from "@/services/server/transport/frame-types";
import { createBoneMeshGeometry } from "./RigidBodyBoneGeometry";
import { prepareModels, preparedModelsMatch, type PreparedModel } from "./prepared-models";
import { prepareBones, writeBoneMatrices, type PreparedBones } from "./prepared-bones";
import { ensureInstanceBuffers } from "./instance-buffers";

import type {InspectionTarget} from "../helpers/viewport3d-types";

const INITIAL_BONES = 256;
/** World quaternions already include rest orientation. Local-only channels hide bones. */
export function RigidBodyBoneRenderer() {
    const {subscribeToModelFrames} = useKeypointsSource();
    const definitions = useModelDefinitionsById();
    const meshRef = useRef<InstancedMesh>(null);
    const pickingRef = useRef(new Map<number, InspectionTarget>());
    const framesRef = useRef<ResolvedModelFrame[]>([]);
    const layoutRef = useRef<PreparedModel[] | null>(null);
    const bonesRef = useRef<PreparedBones[]>([]);
    const rotation = useMemo(() => new Float64Array(9), []);
    const dirtyRef = useRef(false);
    const geometry = useMemo(() => createBoneMeshGeometry(), []);
    const material = useMemo(() => new MeshBasicMaterial({color: "#ffffff"}), []);
    useEffect(() => () => {geometry.dispose(); material.dispose();}, [geometry, material]);
    useEffect(() => subscribeToModelFrames(frames => {framesRef.current = frames; dirtyRef.current = true;}), [subscribeToModelFrames]);
    useEffect(() => {
        const mesh = meshRef.current;
        if (!mesh) return;
        ensureInstanceBuffers(mesh, INITIAL_BONES);
        registerPickingMesh(mesh, {kind: "segment", instanceTargets: pickingRef.current});
        return () => unregisterPickingMesh(mesh);
    }, []);
    useFrame(() => {
        const mesh = meshRef.current, frames = framesRef.current;
        if (!mesh) return;
        if (!layoutRef.current || !preparedModelsMatch(layoutRef.current, frames, definitions.current)) {
            const layout = prepareModels(frames, definitions.current);
            layoutRef.current = layout;
            let slots = 0;
            pickingRef.current.clear();
            bonesRef.current = layout.map(model => {
                const prepared = prepareBones(model, slots);
                for (const segment of model.definition?.segments ?? []) pickingRef.current.set(slots++,
                    {kind: "segment", name: segment.name, modelId: model.modelId, instanceId: model.instanceId});
                return prepared;
            });
            ensureInstanceBuffers(mesh, slots);
            const colors = mesh.instanceColor!.array as Float32Array;
            for (const bones of bonesRef.current) colors.set(bones.colors, bones.baseSlot * 3);
            mesh.instanceColor!.needsUpdate = true;
            dirtyRef.current = true;
        }
        if (!dirtyRef.current) return;
        const matrices = mesh.instanceMatrix.array as Float32Array;
        for (const bones of bonesRef.current) writeBoneMatrices(bones, frames[bones.model.frameIndex], matrices, rotation);
        mesh.instanceMatrix.needsUpdate = true;
        dirtyRef.current = false;
    });
    return <instancedMesh ref={meshRef} args={[geometry, material, INITIAL_BONES]} frustumCulled={false}/>;
}
