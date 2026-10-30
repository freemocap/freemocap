import { DynamicDrawUsage, InstancedBufferAttribute, type InstancedMesh } from 'three';
import { hideMatrix } from './prepared-models';

/** Grow only at a layout change, retaining the mesh and its picking registration. */
export function ensureInstanceBuffers(mesh: InstancedMesh, required: number): void {
    const capacity = Math.max(required, mesh.instanceMatrix.count);
    if (mesh.instanceMatrix.count < capacity) {
        // Dispose the renderer's old GPU allocation before replacing the attribute.
        mesh.dispose();
        mesh.instanceMatrix = new InstancedBufferAttribute(new Float32Array(capacity * 16), 16).setUsage(DynamicDrawUsage);
    }
    if (!mesh.instanceColor || mesh.instanceColor.count < capacity) {
        mesh.instanceColor = new InstancedBufferAttribute(new Float32Array(capacity * 3), 3).setUsage(DynamicDrawUsage);
    }
    const matrices = mesh.instanceMatrix.array as Float32Array;
    for (let i = 0; i < capacity; i++) hideMatrix(matrices, i * 16);
    (mesh.instanceColor.array as Float32Array).fill(0);
    mesh.instanceMatrix.setUsage(DynamicDrawUsage);
    mesh.count = required;
    mesh.instanceMatrix.needsUpdate = true;
    mesh.instanceColor.needsUpdate = true;
}
