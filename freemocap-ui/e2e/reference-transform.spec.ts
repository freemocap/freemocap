import {test, expect} from '@playwright/test';
import {Euler, Matrix4, Quaternion, Vector3} from 'three';
import {transformFields, transformFromFields, TransformRepresentation, validateRigidTransform} from '../src/components/mocap-setup/reference-transform';

test('representations preserve rigid transforms including half turns and Euler singularities', () => {
    for (const rotation of [new Euler(.3, -.4, .7), new Euler(0, Math.PI / 2, .8), new Euler(Math.PI, 0, 0)]) {
        const original = new Matrix4().compose(new Vector3(200, -400, 300), new Quaternion().setFromEuler(rotation), new Vector3(1, 1, 1));
        for (const representation of Object.values(TransformRepresentation)) {
            const restored = transformFromFields(transformFields(original, representation), representation);
            original.elements.forEach((value, index) => expect(restored.elements[index]).toBeCloseTo(value, 6));
        }
    }
});

test('rejects scaling, reflection, invalid homogeneous row and non-unit quaternions', () => {
    expect(() => validateRigidTransform(new Matrix4().makeScale(2, 1, 1))).toThrow();
    expect(() => validateRigidTransform(new Matrix4().makeScale(-1, 1, 1))).toThrow();
    const invalid = new Matrix4(); invalid.elements[3] = .2;
    expect(() => validateRigidTransform(invalid)).toThrow();
    expect(() => transformFromFields([0, 0, 0, 2, 0, 0, 0], TransformRepresentation.Quaternion)).toThrow();
});
