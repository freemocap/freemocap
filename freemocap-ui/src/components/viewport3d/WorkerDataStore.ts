/**
 * Module-level data store for the viewport3d Web Worker.
 *
 * Receives all scene data from the main thread via postMessage and distributes
 * it to React components via subscriptions. For high-frequency keypoints (every
 * frame) a lightweight pub/sub pattern is used (no React state) so that the
 * existing refs + useFrame pattern keeps working. For low-frequency config data
 * (schemas, calibration, visibility) React state is used, driven by this store.
 */

import type { TrackedObjectDefinition } from "@/services/server/server-helpers/tracked-object-definition";
import type { CalibrationConfig, LoadedCalibration } from "@/store/slices/calibration/calibration-types";
import { DEFAULT_VISIBILITY, type Point3d, type ViewportVisibility } from "./helpers/viewport3d-types";
import type { KeypointsFrame, KeypointsSource } from "./KeypointsSourceContext";

// ---------------------------------------------------------------------------
// Shared channel primitive
// ---------------------------------------------------------------------------

type Listener<T> = (data: T) => void;

function makeChannel<T>(initial: T) {
    const subscribers = new Set<Listener<T>>();
    let latest = initial;
    return {
        dispatch(data: T) {
            latest = data;
            subscribers.forEach((cb) => cb(data));
        },
        subscribe(cb: Listener<T>): () => void {
            subscribers.add(cb);
            return () => subscribers.delete(cb);
        },
        getLatest: () => latest,
    };
}

// ---------------------------------------------------------------------------
// Channels
// ---------------------------------------------------------------------------

export interface SchemaState {
    activeTrackerId: string | null;
    trackerSchemas: Record<string, TrackedObjectDefinition>;
}

const DEFAULT_CALIBRATION_CONFIG: CalibrationConfig = {
    charucoBoard: { squares_x: 5, squares_y: 3, square_length_mm: 54 },
    minSharedViewsPerCamera: 200,
    autoStopOnMinViewCount: true,
    solverMethod: "anipose",
    useGroundplane: false,
};

const keypointsChan = makeChannel<KeypointsFrame | null>(null);
const skeletonChan = makeChannel<KeypointsFrame | null>(null);
const schemaChan = makeChannel<SchemaState>({ activeTrackerId: null, trackerSchemas: {} });
const calibChan = makeChannel<LoadedCalibration | null>(null);
const calibConfigChan = makeChannel<CalibrationConfig>(DEFAULT_CALIBRATION_CONFIG);
const visibilityChan = makeChannel<ViewportVisibility>(DEFAULT_VISIBILITY);
const comChan = makeChannel<Point3d | null>(null);
const xcomChan = makeChannel<Point3d | null>(null);

// One-shot command channels (fit/reset camera)
const fitCameraChan = makeChannel<KeypointsFrame | null>(null);
const resetCameraChan = makeChannel<null>(null);

// ---------------------------------------------------------------------------
// Public store — also satisfies KeypointsSource for the KeypointsSourceProvider
// ---------------------------------------------------------------------------

export const workerDataStore: KeypointsSource & {
    subscribeToSchemaState: (cb: Listener<SchemaState>) => () => void;
    getSchemaState: () => SchemaState;
    subscribeToCalibration: (cb: Listener<LoadedCalibration | null>) => () => void;
    getCalibration: () => LoadedCalibration | null;
    subscribeToCalibrationConfig: (cb: Listener<CalibrationConfig>) => () => void;
    getCalibrationConfig: () => CalibrationConfig;
    subscribeToVisibility: (cb: Listener<ViewportVisibility>) => () => void;
    getVisibility: () => ViewportVisibility;
    subscribeToCenterOfMass: (cb: Listener<Point3d | null>) => () => void;
    getLatestCenterOfMass: () => Point3d | null;
    subscribeToXcom: (cb: Listener<Point3d | null>) => () => void;
    getLatestXcom: () => Point3d | null;
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
    subscribeToSkeleton: (cb) => {
        const unsub = skeletonChan.subscribe((f) => { if (f) cb(f); });
        const latest = skeletonChan.getLatest();
        if (latest) cb(latest);
        return unsub;
    },
    getLatestKeypoints: keypointsChan.getLatest,

    // Schema state
    subscribeToSchemaState: schemaChan.subscribe,
    getSchemaState: schemaChan.getLatest,

    // Loaded calibration (camera poses)
    subscribeToCalibration: calibChan.subscribe,
    getCalibration: calibChan.getLatest,

    // Calibration config (charuco board dims, etc.)
    subscribeToCalibrationConfig: calibConfigChan.subscribe,
    getCalibrationConfig: calibConfigChan.getLatest,

    // Viewport visibility toggles
    subscribeToVisibility: visibilityChan.subscribe,
    getVisibility: visibilityChan.getLatest,

    // Center of mass
    subscribeToCenterOfMass: comChan.subscribe,
    getLatestCenterOfMass: comChan.getLatest,

    // Extrapolated center of mass (XCoM)
    subscribeToXcom: xcomChan.subscribe,
    getLatestXcom: xcomChan.getLatest,

    // Camera commands (one-shot)
    subscribeToFitCamera: fitCameraChan.subscribe,
    subscribeToResetCamera: resetCameraChan.subscribe,

    dispatch(type: string, data: unknown) {
        switch (type) {
            case "keypoints":
                keypointsChan.dispatch(data as KeypointsFrame);
                break;
            case "skeleton":
                skeletonChan.dispatch(data as KeypointsFrame);
                break;
            case "schemaState":
                schemaChan.dispatch(data as SchemaState);
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
            case "centerOfMass":
                comChan.dispatch(data as Point3d | null);
                break;
            case "xcom":
                xcomChan.dispatch(data as Point3d | null);
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
