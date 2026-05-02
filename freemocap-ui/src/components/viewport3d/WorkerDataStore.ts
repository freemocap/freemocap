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
import type { KeypointsSource } from "./KeypointsSourceContext";

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

const rawChan = makeChannel<Record<string, Point3d>>({});
const filteredChan = makeChannel<Record<string, Point3d>>({});
const schemaChan = makeChannel<SchemaState>({ activeTrackerId: null, trackerSchemas: {} });
const calibChan = makeChannel<LoadedCalibration | null>(null);
const calibConfigChan = makeChannel<CalibrationConfig>(DEFAULT_CALIBRATION_CONFIG);
const visibilityChan = makeChannel<ViewportVisibility>(DEFAULT_VISIBILITY);

// One-shot command channels (fit/reset camera)
const fitCameraChan = makeChannel<Record<string, Point3d>>({});
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
    subscribeToFitCamera: (cb: Listener<Record<string, Point3d>>) => () => void;
    subscribeToResetCamera: (cb: Listener<null>) => () => void;
    dispatch: (type: string, data: unknown) => void;
} = {
    // KeypointsSource interface
    subscribeToKeypointsRaw: rawChan.subscribe,
    subscribeToKeypointsFiltered: filteredChan.subscribe,
    getLatestKeypointsRaw: rawChan.getLatest,

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

    // Camera commands (one-shot)
    subscribeToFitCamera: fitCameraChan.subscribe,
    subscribeToResetCamera: resetCameraChan.subscribe,

    dispatch(type: string, data: unknown) {
        switch (type) {
            case "keypointsRaw":
                rawChan.dispatch(data as Record<string, Point3d>);
                break;
            case "keypointsFiltered":
                filteredChan.dispatch(data as Record<string, Point3d>);
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
            case "fitCamera":
                fitCameraChan.dispatch(data as Record<string, Point3d>);
                break;
            case "resetCamera":
                resetCameraChan.dispatch(null);
                break;
        }
    },
};
