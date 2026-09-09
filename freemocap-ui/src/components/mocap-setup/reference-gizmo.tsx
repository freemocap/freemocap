import {useLayoutEffect, useRef} from 'react';
import {useFrame, useThree} from '@react-three/fiber';
import {Camera, Object3D, PerspectiveCamera, Vector3} from 'three';
import {OrbitControls} from 'three-stdlib';
import {TransformControls} from 'three/examples/jsm/controls/TransformControls.js';

interface ReferenceGizmoProps {
    object: Object3D;
    onStart: () => void;
    onEnd: () => void;
    onChange: () => void;
}

export function createRoutedTransformControl(camera: Camera, canvas: HTMLCanvasElement): TransformControls {
    const control = new TransformControls(camera, canvas);
    // The shared gesture router owns pointer events; disposal still requires a DOM target.
    control.disconnect();
    return control;
}

export default function ReferenceGizmo(props: ReferenceGizmoProps) {
    const {camera, gl, scene, invalidate, controls: orbit} = useThree();
    const callbacks = useRef(props);
    const controls = useRef<TransformControls[]>([]);
    const position = useRef(new Vector3());
    useLayoutEffect(() => {callbacks.current = props;});
    useFrame(() => {
        if (!(camera instanceof PerspectiveCamera)) return;
        props.object.getWorldPosition(position.current);
        const factor = position.current.distanceTo(camera.position) * Math.min(1.9 * Math.tan(camera.fov * Math.PI / 360) / camera.zoom, 7);
        controls.current.forEach((control, index) => {
            if (factor > 0) control.setSize(4 * (index === 0 ? .45 : .65) / factor);
        });
    });
    useLayoutEffect(() => {
        const canvas = gl.domElement;
        const touchAction = canvas.style.touchAction;
        const move = createRoutedTransformControl(camera, canvas);
        const rotate = createRoutedTransformControl(camera, canvas);
        canvas.style.touchAction = 'none';
        move.setMode('translate');
        rotate.setMode('rotate');
        const pair = [move, rotate];
        controls.current = pair;
        let active: TransformControls | null = null;
        let visible = false;
        const redraw = () => invalidate();
        const change = () => callbacks.current.onChange();
        pair.forEach(control => {
            control.setSpace('local');
            control.attach(props.object);
            scene.add(control.getHelper());
            control.getHelper().visible = false;
            control.addEventListener('change', redraw);
            control.addEventListener('objectChange', change);
        });
        const pointer = (event: PointerEvent, button: number) => {
            const rect = canvas.getBoundingClientRect();
            return new PointerEvent(event.type, {
                clientX: (event.clientX - rect.left) / rect.width * 2 - 1,
                clientY: -(event.clientY - rect.top) / rect.height * 2 + 1,
                button,
            });
        };
        const hover = (event: PointerEvent) => {
            const rect = canvas.getBoundingClientRect();
            const projected = props.object.getWorldPosition(new Vector3()).project(camera);
            const distance = Math.hypot(event.clientX - rect.left - (projected.x + 1) * rect.width / 2,
                event.clientY - rect.top - (1 - projected.y) * rect.height / 2);
            pair.forEach(control => control.pointerHover(pointer(event, -1)));
            visible = distance < 22 || (visible && (distance < 80 || pair.some(control => control.axis !== null)));
            pair.forEach(control => {control.getHelper().visible = visible;});
            invalidate();
        };
        const down = (event: PointerEvent) => {
            if (event.button !== 0) return;
            hover(event);
            if (!visible) return;
            // One gesture owns one operation, even where hit regions overlap.
            const selected = pair.find(control => control.axis !== null);
            if (!selected) return;
            selected.pointerDown(pointer(event, 0));
            if (!selected.dragging) return;
            active = selected;
            event.stopImmediatePropagation();
            canvas.setPointerCapture(event.pointerId);
            if (orbit instanceof OrbitControls) orbit.enabled = false;
            callbacks.current.onStart();
        };
        const motion = (event: PointerEvent) => {
            if (active) {event.stopImmediatePropagation(); active.pointerMove(pointer(event, -1));}
            else hover(event);
        };
        const up = (event: PointerEvent) => {
            if (!active) return;
            event.stopImmediatePropagation();
            active.pointerUp(pointer(event, 0));
            active = null;
            if (canvas.hasPointerCapture(event.pointerId)) canvas.releasePointerCapture(event.pointerId);
            if (orbit instanceof OrbitControls) orbit.enabled = true;
            callbacks.current.onEnd();
            hover(event);
        };
        const leave = () => {
            if (active) return;
            visible = false;
            pair.forEach(control => {control.getHelper().visible = false;});
            invalidate();
        };
        canvas.addEventListener('pointerdown', down, true);
        canvas.addEventListener('pointermove', motion, true);
        canvas.addEventListener('pointerup', up, true);
        canvas.addEventListener('pointercancel', up, true);
        canvas.addEventListener('pointerleave', leave);
        invalidate();
        return () => {
            canvas.removeEventListener('pointerdown', down, true);
            canvas.removeEventListener('pointermove', motion, true);
            canvas.removeEventListener('pointerup', up, true);
            canvas.removeEventListener('pointercancel', up, true);
            canvas.removeEventListener('pointerleave', leave);
            if (orbit instanceof OrbitControls) orbit.enabled = true;
            pair.forEach(control => {
                control.removeEventListener('change', redraw);
                control.removeEventListener('objectChange', change);
                scene.remove(control.getHelper());
                control.detach();
                control.dispose();
            });
            controls.current = [];
            canvas.style.touchAction = touchAction;
        };
    }, [camera, gl, scene, invalidate, orbit, props.object]);
    return null;
}
