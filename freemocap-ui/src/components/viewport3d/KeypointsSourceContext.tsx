import React, {createContext, useContext, useMemo} from "react";
import {useServerOptional} from "@/services/server/server-context";
import type { RotationsFrame, SegmentLengthsFrame } from '@/services/server/transport/frame-types';
import type { ModelDefinition } from '@/services/server/transport/message-contract';

/**
 * Abstraction over "where do 3D keypoints come from". The Streaming panel
 * feeds the renderers from a live WebSocket (via useServer). The Playback
 * panel feeds them from a cached Float32 buffer driven by the playback slider.
 *
 * Renderers pull whichever source is active via `useKeypointsSource()`.
 * If no provider is mounted, the hook transparently falls back to `useServer()`
 * so existing Streaming code keeps working with zero changes at that layer.
 */

/**
 * A single frame of keypoint data in typed-array form.
 *
 * `interleaved` is a Float32Array whose layout depends on which stream produced
 * it. Every PointsFrame delivered to consumers is 3-interleaved `x, y, z`:
 * frame-resolution strips KEYPOINTS_3D's 4th column (reprojection_error) and
 * SEGMENT_ORIGINS is natively 3-column:
 *
 *   keypoints: [x₀, y₀, z₀,  x₁, y₁, z₁, … ]   stride 3
 *   skeleton:  [x₀, y₀, z₀,  x₁, y₁, z₁, … ]   stride 3  (model segment order)
 *
 * Missing / untriangulated points have NaN coords.
 */
export interface KeypointsFrame {
    pointNames: readonly string[];
    interleaved: Float32Array;
}

export type KeypointsCallback = (frame: KeypointsFrame) => void;

export interface KeypointsSource {
    subscribeToKeypoints: (cb: KeypointsCallback) => () => void;
    subscribeToSkeleton: (cb: KeypointsCallback) => () => void;
    getLatestKeypoints: () => KeypointsFrame | null;
    getLatestSkeleton: () => KeypointsFrame | null;
    subscribeToRotations?: (cb: (frame: RotationsFrame) => void) => () => void;
    getLatestRotations?: () => RotationsFrame | null;
    subscribeToSegmentLengths?: (cb: (frame: SegmentLengthsFrame) => void) => () => void;
    getLatestSegmentLengths?: () => SegmentLengthsFrame | null;
    // The model that rides every frame (the rigid-body renderer's name→index map).
    subscribeToModels?: (cb: (models: ModelDefinition[]) => void) => () => void;
    getModels?: () => ModelDefinition[] | null;
}

const KeypointsSourceContext = createContext<KeypointsSource | null>(null);

export const KeypointsSourceProvider: React.FC<{
    source: KeypointsSource;
    children: React.ReactNode;
}> = ({source, children}) => (
    <KeypointsSourceContext.Provider value={source}>
        {children}
    </KeypointsSourceContext.Provider>
);

/**
 * Returns true when a KeypointsSourceProvider is mounted above the consumer
 * (i.e. during playback mode), false when keypoints come from the live server.
 */
export function useHasKeypointsSourceProvider(): boolean {
    return useContext(KeypointsSourceContext) !== null;
}

/**
 * Returns the active keypoints source. Falls back to the live server if no
 * provider is mounted above the consumer.
 */
export function useKeypointsSource(): KeypointsSource {
    const ctx = useContext(KeypointsSourceContext);
    const server = useServerOptional();

    const liveAdapter = useMemo<KeypointsSource | null>(() => {
        if (!server) return null;
        return {
            subscribeToKeypoints: server.subscribeToKeypoints,
            subscribeToSkeleton: server.subscribeToSkeleton,
            getLatestKeypoints: server.getLatestKeypoints,
            getLatestSkeleton: server.getLatestSkeleton,
            subscribeToRotations: server.subscribeToRotations,
            getLatestRotations: server.getLatestRotations,
            subscribeToSegmentLengths: server.subscribeToSegmentLengths,
            getLatestSegmentLengths: server.getLatestSegmentLengths,
            subscribeToModels: server.subscribeToModels,
            getModels: server.getModels,
        };
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [
        server?.subscribeToKeypoints,
        server?.subscribeToSkeleton,
        server?.getLatestKeypoints,
        server?.getLatestSkeleton,
        server?.subscribeToRotations,
        server?.getLatestRotations,
        server?.subscribeToSegmentLengths,
        server?.getLatestSegmentLengths,
        server?.subscribeToModels,
        server?.getModels,
    ]);

    const source = ctx ?? liveAdapter;
    if (!source) throw new Error("No KeypointsSource: mount KeypointsSourceProvider or ServerContextProvider");
    return source;
}
