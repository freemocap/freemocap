import {BufferGeometry, Float32BufferAttribute, Mesh, MeshBasicMaterial, DoubleSide, FrontSide, type Group} from 'three';
import type {ResolvedModelFrame} from '@/services/server/transport/frame-types';
import {writeAttachedPose, type PreparedAttachedLines} from './prepared-attached-lines';
import {XYZ_OFFSETS} from './prepared-models';

export interface PreparedAttachedSurface {
    attachment: PreparedAttachedLines;
    meshes: Mesh<BufferGeometry, MeshBasicMaterial>[];
}

/** One immutable local geometry/material per declared surface; no frame arrays borrowed. */
export function prepareAttachedSurfaces(attachments: readonly PreparedAttachedLines[], group: Group): PreparedAttachedSurface[] {
    return attachments.filter(a => a.surfaces.length > 0).map(attachment => ({attachment,
        meshes: attachment.surfaces.map((surface, index) => {
            const geometry = new BufferGeometry();
            geometry.setAttribute('position', new Float32BufferAttribute(surface.positions, 3));
            geometry.setIndex(surface.indices);
            const material = new MeshBasicMaterial({color: surface.material.color, opacity: surface.material.opacity,
                transparent: true, depthWrite: false, side: surface.double_sided ? DoubleSide : FrontSide});
            // Match the preview's single translucent side-cap pass; no two-sided double blend.
            material.forceSinglePass = true;
            const mesh = new Mesh(geometry, material);
            mesh.userData.attachedSurface = true;
            mesh.matrixAutoUpdate = false; mesh.visible = false; mesh.frustumCulled = false;
            mesh.renderOrder = index + 1;
            group.add(mesh);
            return mesh;
        }),
    }));
}

/** Transform-only update; local vertex/index buffers and materials remain unchanged. */
export function writeAttachedSurfaces(batch: PreparedAttachedSurface, frame: ResolvedModelFrame, rotation: Float64Array): void {
    const scale = writeAttachedPose(batch.attachment, frame, rotation), valid = Number.isFinite(scale);
    for (const mesh of batch.meshes) {
        mesh.visible = valid && mesh.material.opacity > 0;
        if (!valid) continue;
        const points = frame.segmentOrigins!, xyz = points.coordinateOffsets ?? XYZ_OFFSETS;
        const row = batch.attachment.originRow * (points.stride ?? 3);
        mesh.matrix.set(rotation[0]*scale, rotation[1]*scale, rotation[2]*scale, points.data[row+xyz[0]],
            rotation[3]*scale, rotation[4]*scale, rotation[5]*scale, points.data[row+xyz[1]],
            rotation[6]*scale, rotation[7]*scale, rotation[8]*scale, points.data[row+xyz[2]], 0, 0, 0, 1);
        mesh.matrixWorldNeedsUpdate = true;
    }
}

export function disposeAttachedSurfaces(batches: readonly PreparedAttachedSurface[]): void {
    for (const batch of batches) for (const mesh of batch.meshes) {
        mesh.removeFromParent(); mesh.geometry.dispose(); mesh.material.dispose();
    }
}
