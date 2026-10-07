import {useCallback, useEffect, useMemo, useRef} from 'react';
import {useThree} from '@react-three/fiber';
import {Group} from 'three';
import {useKeypointsSource} from '../KeypointsSourceContext';
import {useViewportState} from '../scene/ViewportStateContext';
import type {FittedSkeletonFrame} from '@/services/recording/fitted-skeleton-types';
import {FittedSkeletonInstances} from './FittedSkeletonInstances';

export function FittedSkeletonRenderer() {
    const source = useKeypointsSource();
    const {visibility} = useViewportState();
    const visibilityRef = useRef(visibility); visibilityRef.current = visibility;
    const group = useMemo(() => new Group(), []);
    const frames = useRef<FittedSkeletonFrame[]>([]);
    const instances = useRef<FittedSkeletonInstances[]>([]);
    const invalidate = useThree(state => state.invalidate);
    const update = useCallback(() => {
        for (const item of instances.current) item.update(frames.current.find(f => f.source === item.saved.source),
            visibilityRef.current.savedSkeleton, visibilityRef.current.savedSkeletonAxes);
        invalidate();
    }, [invalidate]);
    useEffect(() => {
        const clear = () => {instances.current.forEach(i => i.dispose()); instances.current = []; group.clear();};
        const unsubDefinitions = source.subscribeToFittedDefinitions?.(definitions => {
            frames.current = [];
            clear(); instances.current = definitions.map(d => new FittedSkeletonInstances(d));
            instances.current.forEach(i => group.add(i.group)); update();
        });
        const unsubFrames = source.subscribeToFittedFrames?.(values => {frames.current = values; update();});
        return () => {unsubDefinitions?.(); unsubFrames?.(); clear();};
    }, [source, group, update]);
    useEffect(update, [update, visibility.savedSkeleton, visibility.savedSkeletonAxes]);
    return <primitive object={group}/>;
}
