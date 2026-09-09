import {useLayoutEffect} from 'react';
import {useThree} from '@react-three/fiber';
import {PerspectiveCamera, Vector3} from 'three';
import {OrbitControls} from 'three-stdlib';

export default function ReferenceFraming({x, y, z, dragging}: {x: number; y: number; z: number; dragging: boolean}) {
    const {camera, controls, size, invalidate} = useThree();
    useLayoutEffect(() => {
        if (dragging || !(controls instanceof OrbitControls)) return;
        if (!(camera instanceof PerspectiveCamera)) throw new Error('Reference preview requires a perspective camera.');
        const origin = new Vector3(x, y, z);
        const center = origin.clone().multiplyScalar(.5);
        const radius = origin.length() * .5 + 1;
        const verticalAngle = camera.fov * Math.PI / 360;
        const horizontalAngle = Math.atan(Math.tan(verticalAngle) * size.width / size.height);
        const distance = radius / Math.sin(Math.min(verticalAngle, horizontalAngle)) * 1.15;
        const direction = camera.position.clone().sub(controls.target).normalize();
        camera.position.copy(center).addScaledVector(direction, distance);
        camera.near = Math.max(.001, distance / 10000);
        camera.far = Math.max(100, distance + radius * 4);
        camera.updateProjectionMatrix();
        controls.target.copy(center);
        controls.update();
        invalidate();
    }, [camera, controls, size.width, size.height, x, y, z, dragging, invalidate]);
    return null;
}
