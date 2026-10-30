/** Delivered-frame cadence over approximately one second, independent of ID gaps. */
export class FrameCadence {
    private readonly timestamps = new Float64Array(240);
    private first = 0;
    private count = 0;
    private lastFrameNumber: number | null = null;

    record(frameNumber: number, now = performance.now()): void {
        if (frameNumber === this.lastFrameNumber) return;
        this.lastFrameNumber = frameNumber;
        while (this.count > 1 && now - this.timestamps[this.first] > 1000) {
            this.first = (this.first + 1) % this.timestamps.length;
            this.count--;
        }
        if (this.count === this.timestamps.length) {
            this.first = (this.first + 1) % this.timestamps.length;
            this.count--;
        }
        this.timestamps[(this.first + this.count) % this.timestamps.length] = now;
        this.count++;
    }

    getFps(now = performance.now()): number | null {
        if (this.count < 2) return null;
        const last = this.timestamps[(this.first + this.count - 1) % this.timestamps.length];
        if (now - last > 1000) return 0;
        const elapsed = last - this.timestamps[this.first];
        return elapsed > 0 ? 1000 * (this.count - 1) / elapsed : null;
    }
}
