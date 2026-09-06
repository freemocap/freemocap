/** Single producer with bounded ownership and backpressure from presentation. */
export class FrameLookahead<T> {
    private readonly queue: T[] = [];
    private stopped = false;
    private next: number;
    private filling: Promise<void> | null = null;
    private failure: unknown;
    constructor(private readonly options: {
        start: number; end: number; capacity: number;
        load: (ordinal: number) => Promise<T>; release: (frame: T) => void;
    }) {
        if (!Number.isSafeInteger(options.capacity) || options.capacity < 1) throw new Error('Invalid lookahead capacity');
        this.next = options.start;
    }
    get size(): number { return this.queue.length; }
    get finished(): boolean { return this.next >= this.options.end && !this.queue.length && !this.filling; }
    async fill(): Promise<void> {
        if (this.failure) throw this.failure;
        if (this.stopped) return;
        if (!this.filling) {
            this.filling = this.produce().finally(() => {this.filling = null;});
        }
        await this.filling;
    }
    take(): T | undefined {
        if (this.failure) throw this.failure;
        return this.queue.shift();
    }
    async close(): Promise<void> {
        this.stopped = true;
        this.queue.splice(0).forEach(this.options.release);
        await this.filling;
    }
    private async produce(): Promise<void> {
        try {
            while (!this.stopped && this.queue.length < this.options.capacity && this.next < this.options.end) {
                const frame = await this.options.load(this.next++);
                if (this.stopped) this.options.release(frame);
                else this.queue.push(frame);
            }
        } catch (error) {this.failure = error; throw error;}
    }
}
