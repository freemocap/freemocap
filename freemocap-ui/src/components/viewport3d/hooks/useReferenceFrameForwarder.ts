import {useEffect} from 'react';
import {useAppSelector} from '@/store';

interface ReferenceFrameTarget {
    postMessage(message: {type: 'referenceTransform'; data: number[] | null}): void;
}

export function useReferenceFrameForwarder(target: ReferenceFrameTarget, isLive: boolean): void {
    const transform = useAppSelector(state => state.realtime.pipelineConfig.aggregator_config.reference_transform);
    useEffect(() => {
        target.postMessage({type: 'referenceTransform', data: isLive ? transform?.matrix ?? null : null});
    }, [target, isLive, transform]);
}
