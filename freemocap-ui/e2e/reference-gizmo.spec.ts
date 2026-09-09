import {expect, test} from '@playwright/test';
import {Group, PerspectiveCamera, Scene} from 'three';
import {createRoutedTransformControl} from '../src/components/mocap-setup/reference-gizmo';

test('routed gizmos release listeners and dispose across repeated mounts', () => {
    const listeners = new Set<EventListenerOrEventListenerObject>();
    const canvas = {
        style: {touchAction: 'auto'},
        addEventListener: (_type: string, listener: EventListenerOrEventListenerObject) => listeners.add(listener),
        removeEventListener: (_type: string, listener: EventListenerOrEventListenerObject) => listeners.delete(listener),
    } as unknown as HTMLCanvasElement;
    const scene = new Scene();
    const object = new Group();
    scene.add(object);
    for (let mount = 0; mount < 3; mount++) {
        const controls = [createRoutedTransformControl(new PerspectiveCamera(), canvas), createRoutedTransformControl(new PerspectiveCamera(), canvas)];
        expect(listeners.size).toBe(0);
        for (const control of controls) {
            control.attach(object);
            scene.add(control.getHelper());
            scene.updateMatrixWorld(true);
            control.detach();
            scene.remove(control.getHelper());
            expect(() => control.dispose()).not.toThrow();
        }
        expect(listeners.size).toBe(0);
        expect(scene.children).toEqual([object]);
    }
});
