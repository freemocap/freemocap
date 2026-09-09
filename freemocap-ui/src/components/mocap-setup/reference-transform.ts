import {Euler, Matrix4, Quaternion, Vector3} from 'three';

export enum TransformRepresentation {
    Euler = 'Euler XYZ · degrees',
    Quaternion = 'Quaternion · W X Y Z',
    AxisAngle = 'Axis–angle · degrees',
    Matrix = '4×4 matrix · row major',
}

const tolerance = 1e-6;
const degrees = 180 / Math.PI;

export function validateRigidTransform(matrix: Matrix4): Matrix4 {
    const e = matrix.elements;
    if (!e.every(Number.isFinite)) throw new Error('Every value must be finite.');
    if (Math.abs(e[3]) > tolerance || Math.abs(e[7]) > tolerance || Math.abs(e[11]) > tolerance || Math.abs(e[15] - 1) > tolerance)
        throw new Error('The last row must be 0, 0, 0, 1.');
    const axes = [new Vector3().setFromMatrixColumn(matrix, 0), new Vector3().setFromMatrixColumn(matrix, 1), new Vector3().setFromMatrixColumn(matrix, 2)];
    if (axes.some(axis => Math.abs(axis.lengthSq() - 1) > tolerance) ||
        Math.abs(axes[0].dot(axes[1])) > tolerance || Math.abs(axes[0].dot(axes[2])) > tolerance || Math.abs(axes[1].dot(axes[2])) > tolerance ||
        Math.abs(matrix.determinant() - 1) > tolerance)
        throw new Error('Rotation must have perpendicular unit axes: no scale, shear, or reflection.');
    return matrix;
}

export function transformFields(matrix: Matrix4, representation: TransformRepresentation): number[] {
    const translation = new Vector3().setFromMatrixPosition(matrix).toArray();
    const q = new Quaternion().setFromRotationMatrix(matrix);
    switch (representation) {
        case TransformRepresentation.Matrix:
            return matrix.clone().transpose().toArray();
        case TransformRepresentation.Euler: {
            const e = new Euler().setFromQuaternion(q, 'XYZ');
            return [...translation, e.x * degrees, e.y * degrees, e.z * degrees];
        }
        case TransformRepresentation.Quaternion:
            return [...translation, q.w, q.x, q.y, q.z];
        case TransformRepresentation.AxisAngle: {
            if (q.w < 0) q.set(-q.x, -q.y, -q.z, -q.w);
            const angle = 2 * Math.acos(Math.min(1, Math.max(-1, q.w)));
            const sine = Math.sin(angle / 2);
            const axis = sine < tolerance ? [0, 0, 1] : [q.x / sine, q.y / sine, q.z / sine];
            return [...translation, ...axis, angle * degrees];
        }
    }
}

export function transformFromFields(values: number[], representation: TransformRepresentation): Matrix4 {
    const count = representation === TransformRepresentation.Matrix ? 16 : representation === TransformRepresentation.Euler ? 6 : 7;
    if (values.length !== count || !values.every(Number.isFinite)) throw new Error(`Enter ${count} finite numbers.`);
    if (representation === TransformRepresentation.Matrix) return validateRigidTransform(new Matrix4().fromArray(values).transpose());
    const translation = new Vector3(...values.slice(0, 3) as [number, number, number]);
    const q = new Quaternion();
    switch (representation) {
        case TransformRepresentation.Euler:
            q.setFromEuler(new Euler(values[3] / degrees, values[4] / degrees, values[5] / degrees, 'XYZ'));
            break;
        case TransformRepresentation.Quaternion:
            q.set(values[4], values[5], values[6], values[3]);
            if (Math.abs(q.lengthSq() - 1) > tolerance) throw new Error('Quaternion must have unit length.');
            break;
        case TransformRepresentation.AxisAngle: {
            const axis = new Vector3(values[3], values[4], values[5]);
            if (Math.abs(axis.lengthSq() - 1) > tolerance) throw new Error('Rotation axis must have unit length.');
            q.setFromAxisAngle(axis, values[6] / degrees);
            break;
        }
    }
    return validateRigidTransform(new Matrix4().compose(translation, q, new Vector3(1, 1, 1)));
}

export function fieldLabels(representation: TransformRepresentation): string[] {
    if (representation === TransformRepresentation.Matrix) return Array.from({length: 16}, (_, i) => `Row ${Math.floor(i / 4) + 1}, column ${i % 4 + 1}`);
    const rotation = representation === TransformRepresentation.Euler ? ['X °', 'Y °', 'Z °'] :
        representation === TransformRepresentation.Quaternion ? ['W', 'X', 'Y', 'Z'] : ['Axis X', 'Axis Y', 'Axis Z', 'Angle °'];
    return ['X mm', 'Y mm', 'Z mm', ...rotation];
}
