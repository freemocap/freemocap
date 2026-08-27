/**
 * Module-level data store for the viewport3d Web Worker.
 *
 * Receives all scene data from the main thread via postMessage and distributes
 * it to React components via subscriptions. For high-frequency keypoints (every
 * frame) a lightweight pub/sub pattern is used (no React state) so that the
 * existing refs + useFrame pattern keeps working. For low-frequency config data
 * (schemas, calibration, visibility) React state is used, driven by this store.
 */

import type { CalibrationConfig, LoadedCalibration } from "@/store/slices/calibration/calibration-types";
import type { ResolvedModelFrame } from "@/services/server/transport/frame-types";
import type { ModelDefinition } from "@/services/server/transport/message-contract";
import { DEFAULT_VISIBILITY, type ViewportVisibility } from "./helpers/viewport3d-types";
import type { KeypointsFrame, KeypointsSource, ModelFramesCallback, ModelsCallback } from "./KeypointsSourceContext";

// ---------------------------------------------------------------------------
// Shared channel primitive
// ---------------------------------------------------------------------------

type Listener<T> = (data: T) => void;

function makeChannel<T>(initial: T, options?: { replayOnSubscribe?: boolean }) {
    const replayOnSubscribe = options?.replayOnSubscribe ?? false;
    const subscribers = new Set<Listener<T>>();
    let latest = initial;
    return {
        dispatch(data: T) {
            latest = data;
            subscribers.forEach((cb) => cb(data));
        },
        subscribe(cb: Listener<T>): () => void {
            // Static channels replay their current value so a subscriber that
            // joins after a worker/provider recreation (HMR swap) receives the
            // held state immediately instead of waiting for a change that may
            // never come on a stable stream. Frame channels stay change-only.
            if (replayOnSubscribe) cb(latest);
            subscribers.add(cb);
            return () => subscribers.delete(cb);
        },
        getLatest: () => latest,
    };
}

// ---------------------------------------------------------------------------
// Channels
// ---------------------------------------------------------------------------

const DEFAULT_CALIBRATION_CONFIG: CalibrationConfig = {
    charucoBoard: { squares_x: 5, squares_y: 3, square_length_mm: 54 },
    minSharedViewsPerCamera: 200,
    autoStopOnMinViewCount: true,
    solverMethod: "anipose",
    useGroundplane: false,
};

const keypointsChan = makeChannel<KeypointsFrame | null>(null);
// Every tracked thing this frame: its model definition, segment origins, landmarks,
// rotations, fitted lengths and derived points. These travel as ONE channel because they
// describe ONE model — split apart, a renderer could pair a person's rotations with a
// board's origins. It also carries the only millimetres in the worker (the model itself is
// dimensionless), so without it every bone draws at unit length.
// Replayed on subscribe: a renderer mounting mid-stream after a worker/HMR swap would
// otherwise show nothing until the next frame.
const modelFramesChan = makeChannel<ResolvedModelFrame[] | null>(null, {replayOnSubscribe: true});
// The STATIC definitions, on their own change-detected channel. Kept apart from the frame
// channel above precisely because they are big: sending them per frame clones every segment
// and landmark across the worker boundary thirty times a second.
const modelsChan = makeChannel<ModelDefinition[] | null>(null, {replayOnSubscribe: true});
const calibChan = makeChannel<LoadedCalibration | null>(null, {replayOnSubscribe: true});
const calibConfigChan = makeChannel<CalibrationConfig>(DEFAULT_CALIBRATION_CONFIG, {replayOnSubscribe: true});
const visibilityChan = makeChannel<ViewportVisibility>(DEFAULT_VISIBILITY);

// One-shot command channels (fit/reset camera)
const fitCameraChan = makeChannel<KeypointsFrame | null>(null);
const resetCameraChan = makeChannel<null>(null);

// ---------------------------------------------------------------------------
// Public store — also satisfies KeypointsSource for the KeypointsSourceProvider
// ---------------------------------------------------------------------------

export const workerDataStore: KeypointsSource & {
    subscribeToCalibration: (cb: Listener<LoadedCalibration | null>) => () => void;
    getCalibration: () => LoadedCalibration | null;
    subscribeToCalibrationConfig: (cb: Listener<CalibrationConfig>) => () => void;
    getCalibrationConfig: () => CalibrationConfig;
    subscribeToVisibility: (cb: Listener<ViewportVisibility>) => () => void;
    getVisibility: () => ViewportVisibility;
    subscribeToFitCamera: (cb: Listener<KeypointsFrame | null>) => () => void;
    subscribeToResetCamera: (cb: Listener<null>) => () => void;
    dispatch: (type: string, data: unknown) => void;
} = {
    // KeypointsSource interface — channels hold KeypointsFrame|null but callbacks expect non-null.
    subscribeToKeypoints: (cb) => {
        const unsub = keypointsChan.subscribe((f) => { if (f) cb(f); });
        const latest = keypointsChan.getLatest();
        if (latest) cb(latest);
        return unsub;
    },
    getLatestKeypoints: keypointsChan.getLatest,

    // The static model definitions (change-detected).
    subscribeToModels: (cb: ModelsCallback) => {
        return modelsChan.subscribe((m) => { if (m) cb(m); });
    },
    getModels: modelsChan.getLatest,

    // Every tracked model's per-frame numbers — the renderers' scene data.
    subscribeToModelFrames: (cb: ModelFramesCallback) => {
        return modelFramesChan.subscribe((m) => { if (m) cb(m); });
    },
    getLatestModelFrames: modelFramesChan.getLatest,

    // Loaded calibration (camera poses)
    subscribeToCalibration: calibChan.subscribe,
    getCalibration: calibChan.getLatest,

    // Calibration config (charuco board dims, etc.)
    subscribeToCalibrationConfig: calibConfigChan.subscribe,
    getCalibrationConfig: calibConfigChan.getLatest,

    // Viewport visibility toggles
    subscribeToVisibility: visibilityChan.subscribe,
    getVisibility: visibilityChan.getLatest,

    // Camera commands (one-shot)
    subscribeToFitCamera: fitCameraChan.subscribe,
    subscribeToResetCamera: resetCameraChan.subscribe,

    dispatch(type: string, data: unknown) {
        switch (type) {
            case "keypoints":
                keypointsChan.dispatch(data as KeypointsFrame);
                break;
            case "models":
                modelsChan.dispatch(data as ModelDefinition[]);
                break;
            case "modelFrames":
                modelFramesChan.dispatch(data as ResolvedModelFrame[]);
                break;
            case "calibration":
                calibChan.dispatch(data as LoadedCalibration | null);
                break;
            case "calibrationConfig":
                calibConfigChan.dispatch(data as CalibrationConfig);
                break;
            case "visibility":
                visibilityChan.dispatch(data as ViewportVisibility);
                break;
            case "fitCamera":
                fitCameraChan.dispatch(data as KeypointsFrame | null);
                break;
            case "resetCamera":
                resetCameraChan.dispatch(null);
                break;
        }
    },
};
