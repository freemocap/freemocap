import {useMemo, useSyncExternalStore} from 'react';
import {Matrix4} from 'three';
import {workerDataStore} from '../WorkerDataStore';

export function useReferenceTransform(): Matrix4 | null {
    const values = useSyncExternalStore(workerDataStore.subscribeToReferenceTransform, workerDataStore.getReferenceTransform);
    return useMemo(() => values ? new Matrix4().fromArray(values).transpose() : null, [values]);
}

export function ReferenceFrame() {
    const transform = useReferenceTransform();
    const inverse = useMemo(() => transform?.clone().invert(), [transform]);
    if (!inverse) return null;
    return <group name="Inverse reference frame" matrix={inverse} matrixAutoUpdate={false}>
        <axesHelper args={[500]}/>
    </group>;
}
