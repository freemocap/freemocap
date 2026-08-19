import type { InstancedMesh } from "three";
import type { InspectionKind } from "../helpers/viewport3d-types";

/**
 * Module-level registry the renderers populate so the ViewportPicker can
 * raycast the instanced meshes (keypoints / landmarks / bones) without the R3F
 * pointer event manager (which is disabled in the worker).
 */

export interface PickingMeshEntry {
    kind: InspectionKind;
    /** instance index -> point/bone name (mutated in place by the renderer). */
    instanceIdToName: Map<number, string>;
}

const registry = new Map<InstancedMesh, PickingMeshEntry>();

export function registerPickingMesh(mesh: InstancedMesh, entry: PickingMeshEntry): void {
    registry.set(mesh, entry);
}

export function unregisterPickingMesh(mesh: InstancedMesh): void {
    registry.delete(mesh);
}

export function getPickingEntries(): ReadonlyMap<InstancedMesh, PickingMeshEntry> {
    return registry;
}
