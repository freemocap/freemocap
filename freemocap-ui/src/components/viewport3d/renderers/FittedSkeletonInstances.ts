import {Color, CylinderGeometry, Group, InstancedMesh, Material, MeshBasicMaterial, MeshStandardMaterial, Object3D, Quaternion, SphereGeometry, Vector3} from 'three';
import type {FittedSkeletonDefinition, FittedSkeletonFrame} from '@/services/recording/fitted-skeleton-types';
import {fittedWorldPoint} from '@/services/recording/fitted-skeleton';
import {registerPickingMesh, unregisterPickingMesh} from './PickingRegistry';
import {AXIS_HEX, LAYER_HEX} from '../helpers/layer-colors';

const UP = new Vector3(0, 1, 0);
const AXES = [new Vector3(1, 0, 0), new Vector3(0, 1, 0), new Vector3(0, 0, 1)];
const COLORS = AXIS_HEX;

/** Saved segment transforms, drawn independently of the original reconstruction. */
export class FittedSkeletonInstances {
    readonly group = new Group();
    readonly sticks: InstancedMesh;
    readonly origins: InstancedMesh;
    readonly axes: InstancedMesh;
    private readonly rods: {body: number; point: number}[] = [];
    private readonly dummy = new Object3D();
    private readonly radii: number[];
    private readonly stickNames = new Map<number, string>();
    private readonly originNames = new Map<number, string>();

    constructor(readonly saved: FittedSkeletonDefinition) {
        const geometry = saved.definition.geometry;
        if (geometry.names.length !== geometry.display.length || geometry.names.length !== geometry.display_names.length ||
            geometry.names.length !== geometry.references.length || geometry.display.some((v, b) => v.length !== geometry.display_names[b].length)) {
            throw new Error('Saved fitted geometry has inconsistent segment/landmark arrays');
        }
        this.radii = geometry.display.map(points => Math.max(1, Math.min(3, Math.max(0, ...points.map(p => Math.hypot(...p))) * 0.025)));
        geometry.display.forEach((points, body) => points.forEach((p, point) => {
            if (Math.hypot(...p) > 1e-8) this.rods.push({body, point});
        }));
        this.sticks = new InstancedMesh(new CylinderGeometry(1, 1, 1, 8), new MeshStandardMaterial({color: LAYER_HEX.savedSkeleton, roughness: 0.65, metalness: 0, emissiveIntensity: 0}), Math.max(1, this.rods.length));
        this.origins = new InstancedMesh(new SphereGeometry(1, 10, 6), new MeshStandardMaterial({color: LAYER_HEX.savedSkeleton, roughness: 0.65, metalness: 0, emissiveIntensity: 0}), geometry.names.length);
        this.axes = new InstancedMesh(new CylinderGeometry(1, 1, 1, 6), new MeshBasicMaterial(), geometry.names.length * 3);
        for (let b = 0; b < geometry.names.length; b++) for (let a = 0; a < 3; a++) this.axes.setColorAt(b * 3 + a, new Color(COLORS[a]));
        for (const mesh of [this.sticks, this.origins, this.axes]) {mesh.count = 0; mesh.frustumCulled = false; this.group.add(mesh);}
        registerPickingMesh(this.sticks, {kind: 'segment', instanceIdToName: this.stickNames});
        registerPickingMesh(this.origins, {kind: 'segment', instanceIdToName: this.originNames});
    }

    private rod(mesh: InstancedMesh, index: number, from: Vector3, to: Vector3, radius: number): void {
        const delta = to.clone().sub(from);
        this.dummy.position.copy(from).add(to).multiplyScalar(0.5);
        this.dummy.quaternion.setFromUnitVectors(UP, delta.clone().normalize());
        this.dummy.scale.set(radius, delta.length(), radius);
        this.dummy.updateMatrix(); mesh.setMatrixAt(index, this.dummy.matrix);
    }

    update(frame: FittedSkeletonFrame | undefined, sticksVisible: boolean, axesVisible: boolean): void {
        const geometry = this.saved.definition.geometry;
        this.sticks.count = this.origins.count = this.axes.count = 0;
        this.stickNames.clear(); this.originNames.clear();
        if (!frame || (!sticksVisible && !axesVisible)) return;
        for (const {body, point} of this.rods) {
            if (!sticksVisible || !frame.validSegments[body]) continue;
            const i = this.sticks.count++;
            this.stickNames.set(i, `Fitted ${geometry.names[body]} → ${geometry.display_names[body][point]}`);
            this.rod(this.sticks, i, new Vector3().fromArray(frame.origins, body * 3),
                fittedWorldPoint(this.saved.definition, frame, body, geometry.display[body][point]), this.radii[body] * 0.75);
        }
        geometry.names.forEach((_, b) => {
            if (!frame.validSegments[b]) return;
            const originIndex = this.origins.count++;
            this.originNames.set(originIndex, `Fitted ${geometry.names[b]} origin`);
            const origin = new Vector3().fromArray(frame.origins, b * 3);
            this.dummy.position.copy(origin); this.dummy.quaternion.identity(); this.dummy.scale.setScalar(this.radii[b] * 1.8 * 0.75);
            this.dummy.updateMatrix(); this.origins.setMatrixAt(originIndex, this.dummy.matrix);
            if (!axesVisible) return;
            const q = frame.quaternions.subarray(b * 4, b * 4 + 4);
            const quaternion = new Quaternion(q[1], q[2], q[3], q[0]);
            const axisLength = this.radii[b] * 12;
            AXES.forEach((axis, a) => {
                const index = this.axes.count++;
                this.axes.setColorAt(index, new Color(COLORS[a]));
                this.rod(this.axes, index, origin,
                    axis.clone().applyQuaternion(quaternion).multiplyScalar(axisLength).add(origin), this.radii[b] * 0.3);
            });
        });
        for (const mesh of [this.sticks, this.origins, this.axes]) mesh.instanceMatrix.needsUpdate = true;
    }

    dispose(): void {
        unregisterPickingMesh(this.sticks); unregisterPickingMesh(this.origins);
        for (const mesh of [this.sticks, this.origins, this.axes]) {
            mesh.geometry.dispose(); (mesh.material as Material).dispose(); mesh.dispose();
        }
        this.group.clear();
    }
}
