import {Bone, BufferGeometry, Color, Float32BufferAttribute, Matrix4, MeshStandardMaterial, Skeleton, SkinnedMesh, Uint16BufferAttribute} from 'three';
import type {ModelDefinition} from '@/services/server/transport/message-contract';
import type {ResolvedModelFrame} from '@/services/server/transport/frame-types';
import {finitePoint, prepareRows, XYZ_OFFSETS} from '../prepared-models';

export interface SkellyAsset {
    version: number;
    coordinateSystem: string;
    source: string;
    sourceSha256: string;
    landmarks: Record<string, number[]>;
    materials: {name: string; inputs: Record<string, number | number[]>}[];
    parts: {name: string; parent: string | null; authoredLength: number; restOrientation: number[];
        positions: number[]; indices: number[]; faceMaterials: number[]}[];
}

const close = (a: number, b: number) => Number.isFinite(a) && Math.abs(a - b) < 1e-6;

/** This artwork is bound to an explicit authored model, never to matching names alone. */
export function skellyCompatible(asset: SkellyAsset, model: ModelDefinition | undefined): boolean {
    if (!model || asset.version !== 1 || asset.coordinateSystem !== 'blender_x_right_y_forward_z_up') return false;
    const landmarks = new Map(model.landmarks.map(p => [p.name, p.rest_position]));
    for (const [name, expected] of Object.entries(asset.landmarks)) {
        const actual = landmarks.get(name);
        if (!actual || !expected.every((v, i) => close(actual[i], v))) return false;
    }
    const segments = new Map(model.segments.map(s => [s.name, s]));
    return asset.parts.every(part => {
        const segment = segments.get(part.name);
        if (!segment || segment.parent !== part.parent || !close(segment.length_proportion, part.authoredLength)) return false;
        // q and -q describe the same rotation.
        const sign = segment.rest_orientation.reduce((sum, v, i) => sum + v * part.restOrientation[i], 0) < 0 ? -1 : 1;
        return part.restOrientation.every((v, i) => close(segment.rest_orientation[i] * sign, v));
    });
}

export function createSkellyMesh(asset: SkellyAsset): SkinnedMesh {
    const positions: number[] = [], joints: number[] = [], weights: number[] = [];
    const triangles = asset.materials.map(() => [] as number[]);
    asset.parts.forEach((part, bone) => {
        const offset = positions.length / 3;
        positions.push(...part.positions);
        for (let i = 0; i < part.positions.length / 3; i++) {
            joints.push(bone, 0, 0, 0); weights.push(1, 0, 0, 0);
        }
        part.faceMaterials.forEach((material, face) => {
            for (let corner = 0; corner < 3; corner++) triangles[material].push(offset + part.indices[face * 3 + corner]);
        });
    });
    const geometry = new BufferGeometry();
    geometry.setAttribute('position', new Float32BufferAttribute(positions, 3));
    geometry.setAttribute('skinIndex', new Uint16BufferAttribute(joints, 4));
    geometry.setAttribute('skinWeight', new Float32BufferAttribute(weights, 4));
    geometry.setIndex(triangles.flat());
    let start = 0;
    triangles.forEach((indices, material) => {geometry.addGroup(start, indices.length, material); start += indices.length;});
    geometry.computeVertexNormals();
    const materials = asset.materials.map(source => {
        const values = source.inputs, color = values['Base Color'] as number[];
        const emission = values['Emission Color'] as number[];
        return new MeshStandardMaterial({name: source.name, color: new Color().setRGB(color[0], color[1], color[2]),
            metalness: values.Metallic as number, roughness: values.Roughness as number,
            opacity: values.Alpha as number, transparent: (values.Alpha as number) < 1,
            emissive: new Color().setRGB(emission[0], emission[1], emission[2]), emissiveIntensity: values['Emission Strength'] as number});
    });
    const mesh = new SkinnedMesh(geometry, materials);
    const bones = asset.parts.map(part => {const bone = new Bone(); bone.name = part.name; bone.scale.setScalar(0); mesh.add(bone); return bone;});
    mesh.bind(new Skeleton(bones, bones.map(() => new Matrix4())), new Matrix4());
    mesh.frustumCulled = false;
    mesh.name = 'Skelly artwork';
    return mesh;
}

export interface SkellyRows {origins: Int32Array; rotations: Int32Array; lengths: Int32Array}
export function prepareSkellyRows(asset: SkellyAsset, frame: ResolvedModelFrame): SkellyRows {
    const names = asset.parts.map(part => part.name);
    return {origins: prepareRows(frame.segmentOrigins?.names, names), rotations: prepareRows(frame.rotations?.boneNames, names),
        lengths: prepareRows(frame.segmentLengths?.names, names)};
}

/** Borrow current frame arrays for this call only; only the resulting bone transforms survive. */
export function updateSkellyPose(mesh: SkinnedMesh, asset: SkellyAsset, rows: SkellyRows, frame: ResolvedModelFrame): void {
    const origins = frame.segmentOrigins?.data, quaternions = frame.rotations?.worldQuaternions;
    const stride = frame.segmentOrigins?.stride ?? 3, coordinates = frame.segmentOrigins?.coordinateOffsets ?? XYZ_OFFSETS;
    for (let i = 0; i < asset.parts.length; i++) {
        const bone = mesh.skeleton.bones[i], o = rows.origins[i] * stride, q = rows.rotations[i] * 4;
        const length = frame.segmentLengths?.data[rows.lengths[i]];
        const scale = length !== undefined ? length / asset.parts[i].authoredLength : frame.segmentLengths?.fittedScaleMm ?? frame.fittedScaleMm;
        if (!finitePoint(origins, o, coordinates) || !finitePoint(quaternions, q) || !Number.isFinite(quaternions?.[q + 3])
            || scale == null || !Number.isFinite(scale) || scale <= 0) {bone.scale.setScalar(0); continue;}
        bone.position.set(origins![o + coordinates[0]], origins![o + coordinates[1]], origins![o + coordinates[2]]);
        bone.quaternion.set(quaternions![q + 1], quaternions![q + 2], quaternions![q + 3], quaternions![q]);
        bone.scale.setScalar(scale);
    }
}

export function disposeSkellyMesh(mesh: SkinnedMesh): void {
    mesh.geometry.dispose(); mesh.skeleton.dispose();
    for (const material of mesh.material as MeshStandardMaterial[]) material.dispose();
}
