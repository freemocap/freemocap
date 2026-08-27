import React, {createContext, useContext, useEffect, useMemo, useRef, useState} from "react";
import {useServerOptional} from "@/services/server/server-context";
import type { ResolvedModelFrame } from '@/services/server/transport/frame-types';
import type { ModelDefinition } from '@/services/server/transport/message-contract';

/**
 * Abstraction over "where does 3D scene data come from". The Streaming panel
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
 * `interleaved` is 3-interleaved `x, y, z` (stride 3): frame-resolution strips
 * KEYPOINTS_3D's 4th column (reprojection_error). Missing / untriangulated points
 * have NaN coords.
 */
export interface KeypointsFrame {
    pointNames: readonly string[];
    interleaved: Float32Array;
}

export type KeypointsCallback = (frame: KeypointsFrame) => void;
export type ModelFramesCallback = (models: ResolvedModelFrame[]) => void;
export type ModelsCallback = (models: ModelDefinition[]) => void;

/**
 * A source of scene data.
 *
 * `keypoints` are raw measurements — every detector's triangulated points, merged.
 * `modelFrames` are the RECONSTRUCTIONS: one entry per tracked thing this frame, each
 * carrying its own model definition alongside its own origins / landmarks / rotations /
 * lengths / derived points. A tracked person and a tracked charuco board are two entries,
 * so every renderer iterates rather than reading "the" skeleton — which is the whole
 * reason these five channels travel together instead of separately.
 */
export interface KeypointsSource {
    subscribeToKeypoints: (cb: KeypointsCallback) => () => void;
    getLatestKeypoints: () => KeypointsFrame | null;
    /** The STATIC model definitions — segments, landmarks, connections, groups. Emitted only
     *  when the model set actually changes, never per frame: they are large, and cloning
     *  them to the viewport worker every frame is what turns 30fps into single digits. */
    subscribeToModels: (cb: ModelsCallback) => () => void;
    getModels: () => ModelDefinition[] | null;
    /** The per-frame numbers, one entry per tracked model. Join to a definition by `modelId`. */
    subscribeToModelFrames: (cb: ModelFramesCallback) => () => void;
    getLatestModelFrames: () => ResolvedModelFrame[] | null;
}

/** Index the current model definitions by id, for the per-frame join.
 *
 *  Kept in a ref and rebuilt only on a model change, so the hot path is a Map lookup rather
 *  than anything that allocates. */
export function useModelDefinitionsById(): React.RefObject<Map<string, ModelDefinition>> {
    const source = useKeypointsSource();
    const byId = useRef<Map<string, ModelDefinition>>(new Map());
    const [, setRevision] = useState(0);

    useEffect(() => {
        const apply = (models: ModelDefinition[]): void => {
            byId.current = new Map(models.map((m) => [m.model_id, m]));
            setRevision((r) => r + 1);
        };
        const existing = source.getModels();
        if (existing) apply(existing);
        return source.subscribeToModels(apply);
    }, [source]);

    return byId;
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
            getLatestKeypoints: server.getLatestKeypoints,
            subscribeToModels: server.subscribeToModels,
            getModels: server.getModels,
            subscribeToModelFrames: server.subscribeToModelFrames,
            getLatestModelFrames: server.getLatestModelFrames,
        };
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [
        server?.subscribeToKeypoints,
        server?.getLatestKeypoints,
        server?.subscribeToModels,
        server?.getModels,
        server?.subscribeToModelFrames,
        server?.getLatestModelFrames,
    ]);

    const source = ctx ?? liveAdapter;
    if (!source) throw new Error("No KeypointsSource: mount KeypointsSourceProvider or ServerContextProvider");
    return source;
}
