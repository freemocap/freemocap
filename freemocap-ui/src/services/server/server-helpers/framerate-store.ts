// src/services/server/server-helpers/framerate-store.ts

import {
    DetailedFramerate,
    MAX_DURATION_HISTORY,
    TimestampedRingBuffer,
    TimestampedSample,
    WindowedStats,
} from "@/services/server/server-helpers/sample-window-stats";

export type {DetailedFramerate, TimestampedSample} from "@/services/server/server-helpers/sample-window-stats";

/** Snapshot of all framerate data, returned by getSnapshot(). */
export type FramerateSnapshot = {
    currentBackendFramerate: DetailedFramerate | null;
    currentFrontendFramerate: DetailedFramerate | null;
    aggregateBackendFramerate: DetailedFramerate | null;
    aggregateFrontendFramerate: DetailedFramerate | null;
    recentFrontendDurations: TimestampedSample[];
    recentBackendDurations: TimestampedSample[];
    lastBackendSampleTimestamp: number;
    lastFrontendSampleTimestamp: number;
};

/**
 * Mutable store for streaming framerate telemetry.
 * Lives in a ref — no Redux, no immutable copies, no re-renders on every update.
 * Components poll via getSnapshot() on their own schedule.
 *
 * Aggregate statistics are computed from the windowed ring buffer on each snapshot (~4Hz).
 */
export class FramerateStore {
    currentBackendFramerate: DetailedFramerate | null = null;
    currentFrontendFramerate: DetailedFramerate | null = null;

    private _recentFrontendDurations = new TimestampedRingBuffer(MAX_DURATION_HISTORY);
    private _recentBackendDurations = new TimestampedRingBuffer(MAX_DURATION_HISTORY);
    private _frontendStats = new WindowedStats(this._recentFrontendDurations, MAX_DURATION_HISTORY);
    private _backendStats = new WindowedStats(this._recentBackendDurations, MAX_DURATION_HISTORY);

    private _lastBackendSampleTimestamp = 0;
    private _lastFrontendSampleTimestamp = 0;

    private _writeVersion = 0;
    private _snapshotVersion = -1;
    private _cachedSnapshot: FramerateSnapshot | null = null;

    updateBackend(data: DetailedFramerate): void {
        this.currentBackendFramerate = data;
        this._writeVersion++;
        if (data.mean_frame_duration_ms > 0) {
            this._recentBackendDurations.push(Date.now(), data.mean_frame_duration_ms);
            this._lastBackendSampleTimestamp = Date.now();
        }
    }

    updateFrontend(data: DetailedFramerate): void {
        this.currentFrontendFramerate = data;
        this._writeVersion++;
        if (data.mean_frame_duration_ms > 0) {
            this._recentFrontendDurations.push(Date.now(), data.mean_frame_duration_ms);
            this._lastFrontendSampleTimestamp = Date.now();
        }
    }

    /** Returns a snapshot for React components to read during render.
     *  Cached until the next update so polling callers get the same object. */
    getSnapshot(): FramerateSnapshot {
        if (this._cachedSnapshot && this._snapshotVersion === this._writeVersion) {
            return this._cachedSnapshot;
        }

        this._cachedSnapshot = {
            currentBackendFramerate: this.currentBackendFramerate,
            currentFrontendFramerate: this.currentFrontendFramerate,
            aggregateBackendFramerate: this._backendStats.computeAggregate(
                this.currentBackendFramerate?.framerate_source ?? "Server",
            ),
            aggregateFrontendFramerate: this._frontendStats.computeAggregate(
                this.currentFrontendFramerate?.framerate_source ?? "Display",
            ),
            recentFrontendDurations: this._recentFrontendDurations.toArray(),
            recentBackendDurations: this._recentBackendDurations.toArray(),
            lastBackendSampleTimestamp: this._lastBackendSampleTimestamp,
            lastFrontendSampleTimestamp: this._lastFrontendSampleTimestamp,
        };
        this._snapshotVersion = this._writeVersion;
        return this._cachedSnapshot;
    }

    clear(): void {
        this.currentBackendFramerate = null;
        this.currentFrontendFramerate = null;
        this._recentFrontendDurations.clear();
        this._recentBackendDurations.clear();
        this._lastBackendSampleTimestamp = 0;
        this._lastFrontendSampleTimestamp = 0;
        this._writeVersion++;
        this._cachedSnapshot = null;
        this._snapshotVersion = -1;
    }
}
