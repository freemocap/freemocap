/**
 * React context that exposes per-scene configuration to renderer components
 * running inside the viewport3d Web Worker.
 *
 * Renderers call `useWorkerData()` instead of `useServer()` + `useAppSelector()`
 * so they work transparently whether they run on the main thread (future) or in
 * a worker (current). The provider subscribes to `workerDataStore` and promotes
 * low-frequency config changes into React state so components re-render only when
 * schemas / calibration actually change — not on every keyframe.
 *
 * Visibility is handled separately: `WorkerVisibilitySync` listens to the store
 * and forwards visibility changes into the nearest `ViewportStateProvider`.
 */

import React, {
    createContext,
    useCallback,
    useContext,
    useEffect,
    useMemo,
    useState,
} from "react";
import type {
    CalibrationConfig,
    LoadedCalibration,
} from "@/store/slices/calibration/calibration-types";
import { workerDataStore } from "./WorkerDataStore";
import { useViewportState } from "./scene/ViewportStateContext";

// ---------------------------------------------------------------------------
// Context value shape
// ---------------------------------------------------------------------------

export interface WorkerDataContextValue {
    calibrationConfig: CalibrationConfig;
    loadedCalibration: LoadedCalibration | null;
}

const WorkerDataContext = createContext<WorkerDataContextValue | null>(null);

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function WorkerDataProvider({ children }: { children: React.ReactNode }) {
    const [loadedCalibration, setLoadedCalibration] = useState<LoadedCalibration | null>(
        workerDataStore.getCalibration,
    );
    const [calibrationConfig, setCalibrationConfig] = useState<CalibrationConfig>(
        workerDataStore.getCalibrationConfig,
    );

    useEffect(() => {
        const unsubs = [
            workerDataStore.subscribeToCalibration(setLoadedCalibration),
            workerDataStore.subscribeToCalibrationConfig(setCalibrationConfig),
        ];
        return () => unsubs.forEach((fn) => fn());
    }, []);

    const value = useMemo<WorkerDataContextValue>(
        () => ({
            calibrationConfig,
            loadedCalibration,
        }),
        [calibrationConfig, loadedCalibration],
    );

    return (
        <WorkerDataContext.Provider value={value}>
            {children}
        </WorkerDataContext.Provider>
    );
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useWorkerData(): WorkerDataContextValue {
    const ctx = useContext(WorkerDataContext);
    if (!ctx) throw new Error("useWorkerData must be used within WorkerDataProvider");
    return ctx;
}

// ---------------------------------------------------------------------------
// WorkerVisibilitySync — bridge store visibility into ViewportStateContext
// Must be rendered inside both WorkerDataProvider and ViewportStateProvider.
// ---------------------------------------------------------------------------

export function WorkerVisibilitySync() {
    const { setVisibility } = useViewportState();

    useEffect(() => {
        // Immediately apply whatever visibility the main thread already sent.
        setVisibility(workerDataStore.getVisibility());
        return workerDataStore.subscribeToVisibility(setVisibility);
    }, [setVisibility]);

    return null;
}

