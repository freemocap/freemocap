// Shared ring buffer + windowed statistics for FramerateStore and PipelineTimingStore.

export const MAX_DURATION_HISTORY = 1000;

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

/**
 * Fixed-capacity ring buffer for timestamped numeric samples.
 * O(1) push. toArray() reuses its output array when possible to reduce GC pressure.
 */
export class TimestampedRingBuffer {
    private readonly timestamps: Float64Array;
    private readonly values: Float64Array;
    private writeIndex: number = 0;
    private count: number = 0;

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

    toArray(): TimestampedSample[] {
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
 */
export class WindowedStats {
    private _buffer: TimestampedRingBuffer;
    private _valuesBuf: Float64Array;

    constructor(buffer: TimestampedRingBuffer, capacity: number) {
        this._buffer = buffer;
        this._valuesBuf = new Float64Array(capacity);
    }

    computeAggregate(source: string): DetailedFramerate | null {
        const count = this._buffer.getCount();
        if (count === 0) return null;

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
