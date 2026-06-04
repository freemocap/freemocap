// src/services/server/server-helpers/framerate-store.ts

const MAX_DURATION_HISTORY = 1000;

/** Matches the shape sent by the Python backend's CurrentFramerate.model_dump() */
export type DetailedFramerate = {
    mean_frame_duration_ms: number;
    mean_frames_per_second: number;
    frame_duration_max: number;
    frame_duration_min: number;
    frame_duration_mean: number;
    frame_duration_stddev: number;
    frame_duration_median: number;
    frame_duration_coefficient_of_variation: number;
    calculation_window_size: number;
    framerate_source: string;
};

/** A single data point with the real timestamp of when it was recorded. */
export type TimestampedSample = {
    timestamp: number;
    value: number;
};

/** Snapshot of all framerate data, returned by getSnapshot(). */
export type FramerateSnapshot = {
    currentBackendFramerate: DetailedFramerate | null;
    currentFrontendFramerate: DetailedFramerate | null;
    aggregateBackendFramerate: DetailedFramerate | null;
    aggregateFrontendFramerate: DetailedFramerate | null;
    recentFrontendDurations: TimestampedSample[];
    recentBackendDurations: TimestampedSample[];
};

/**
 * Fixed-capacity ring buffer for timestamped numeric samples.
 * O(1) push. toArray() reuses its output array when possible to reduce GC pressure.
 */
class TimestampedRingBuffer {
    private readonly timestamps: Float64Array;
    private readonly values: Float64Array;
    private writeIndex: number = 0;
    private count: number = 0;

    /** Cached array from the last toArray() call — reused if count hasn't changed. */
    private _cachedArray: TimestampedSample[] | null = null;
    private _cachedVersion: number = 0;
    private _version: number = 0;

    constructor(capacity: number) {
        this.timestamps = new Float64Array(capacity);
        this.values = new Float64Array(capacity);
    }

    push(timestamp: number, value: number): void {
        this.timestamps[this.writeIndex] = timestamp;
        this.values[this.writeIndex] = value;
        this.writeIndex = (this.writeIndex + 1) % this.timestamps.length;
        if (this.count < this.timestamps.length) {
            this.count++;
        }
        this._version++;
    }

    /** Return contents in chronological order (oldest → newest). */
    toArray(): TimestampedSample[] {
        // Return cached array if no writes since last call
        if (this._cachedArray !== null && this._cachedVersion === this._version) {
            return this._cachedArray;
        }

        const result = new Array<TimestampedSample>(this.count);
        if (this.count < this.timestamps.length) {
            for (let i = 0; i < this.count; i++) {
                result[i] = {timestamp: this.timestamps[i], value: this.values[i]};
            }
        } else {
            for (let i = 0; i < this.count; i++) {
                const idx = (this.writeIndex + i) % this.timestamps.length;
                result[i] = {timestamp: this.timestamps[idx], value: this.values[idx]};
            }
        }

        this._cachedArray = result;
        this._cachedVersion = this._version;
        return result;
    }

    /** Copy current values into a Float64Array in chronological order (for stats computation). */
    valuesToFloat64Array(): Float64Array {
        const result = new Float64Array(this.count);
        this.copyValuesInto(result);
        return result;
    }

    /** Copy current values in chronological order into the provided array.
     *  The target must have at least `count` elements. */
    copyValuesInto(target: Float64Array): void {
        if (this.count < this.values.length) {
            for (let i = 0; i < this.count; i++) {
                target[i] = this.values[i];
            }
        } else {
            for (let i = 0; i < this.count; i++) {
                target[i] = this.values[(this.writeIndex + i) % this.values.length];
            }
        }
    }

    getCount(): number {
        return this.count;
    }

    clear(): void {
        this.writeIndex = 0;
        this.count = 0;
        this._cachedArray = null;
        this._version++;
    }
}

/**
 * Computes statistics over the current contents of a ring buffer.
 * All stats reflect only the windowed data (last MAX_DURATION_HISTORY samples),
 * not all-time accumulations.
 */
class WindowedStats {
    private _buffer: TimestampedRingBuffer;
    /** Reusable typed array to avoid allocating a fresh one on every snapshot. */
    private _valuesBuf: Float64Array;

    constructor(buffer: TimestampedRingBuffer, capacity: number) {
        this._buffer = buffer;
        this._valuesBuf = new Float64Array(capacity);
    }

    /** Compute stats from the ring buffer's current window. */
    computeAggregate(source: string): DetailedFramerate | null {
        const count = this._buffer.getCount();
        if (count === 0) return null;

        // Reuse the pre-allocated buffer, only reallocating if capacity grew
        if (this._valuesBuf.length < count) {
            this._valuesBuf = new Float64Array(count);
        }
        const values = this._valuesBuf.subarray(0, count);
        this._buffer.copyValuesInto(values);

        let sum = 0;
        let min = Infinity;
        let max = -Infinity;
        for (let i = 0; i < values.length; i++) {
            const v = values[i];
            sum += v;
            if (v < min) min = v;
            if (v > max) max = v;
        }

        const mean = sum / count;

        let m2 = 0;
        for (let i = 0; i < values.length; i++) {
            const d = values[i] - mean;
            m2 += d * d;
        }
        const variance = count > 1 ? m2 / count : 0;
        const stddev = Math.sqrt(variance);
        const cv = mean > 0 ? stddev / mean : 0;

        // Sort for median
        values.sort();
        const median = count % 2 === 0
            ? (values[count / 2 - 1] + values[count / 2]) / 2
            : values[Math.floor(count / 2)];

        return {
            mean_frame_duration_ms: mean,
            mean_frames_per_second: mean > 0 ? 1000 / mean : 0,
            frame_duration_mean: mean,
            frame_duration_median: median,
            frame_duration_min: min,
            frame_duration_max: max,
            frame_duration_stddev: stddev,
            frame_duration_coefficient_of_variation: cv,
            calculation_window_size: count,
            framerate_source: source,
        };
    }
}

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

    updateBackend(data: DetailedFramerate): void {
        this.currentBackendFramerate = data;
        if (data.mean_frame_duration_ms > 0) {
            this._recentBackendDurations.push(Date.now(), data.mean_frame_duration_ms);
        }
    }

    updateFrontend(data: DetailedFramerate): void {
        this.currentFrontendFramerate = data;
        if (data.mean_frame_duration_ms > 0) {
            this._recentFrontendDurations.push(Date.now(), data.mean_frame_duration_ms);
        }
    }

    /** Returns a snapshot for React components to read during render. */
    getSnapshot(): FramerateSnapshot {
        return {
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
        };
    }

    clear(): void {
        this.currentBackendFramerate = null;
        this.currentFrontendFramerate = null;
        this._recentFrontendDurations.clear();
        this._recentBackendDurations.clear();
    }
}
