/** Single producer with bounded ownership and backpressure from presentation. */
export class FrameLookahead<T> {
    private readonly queue: {ordinal: number; frame: T}[] = [];
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
    get firstOrdinal(): number | undefined {return this.queue[0]?.ordinal;}
    get size(): number { return this.queue.length; }
    get buffered(): readonly T[] {return this.queue.map(entry => entry.frame);}
    get finished(): boolean { return this.next >= this.options.end && !this.queue.length && !this.filling; }
    async fill(): Promise<void> {
        if (this.failure) throw this.failure;
        if (this.stopped || (this.next >= this.options.end && !this.filling)) return;
        if (!this.filling) {
            this.filling = this.produce().finally(() => {this.filling = null;});
        }
        await this.filling;
    }
    /** Select the newest prepared frame due now; decoding always advances sequentially. */
    takeDue(ordinal: number): T | undefined {
        if (this.failure) throw this.failure;
        let selected: T | undefined;
        while (this.queue.length && this.queue[0].ordinal <= ordinal) {
            if (selected !== undefined) this.options.release(selected);
            selected = this.queue.shift()!.frame;
        }
        return selected;
    }
    async close(): Promise<void> {
        this.stopped = true;
        this.queue.splice(0).forEach(entry => this.options.release(entry.frame));
        await this.filling;
    }
    private async produce(): Promise<void> {
        try {
            while (!this.stopped && this.queue.length < this.options.capacity && this.next < this.options.end) {
                const ordinal = this.next++;
                const frame = await this.options.load(ordinal);
                if (this.stopped) this.options.release(frame);
                else this.queue.push({ordinal, frame});
            }
        } catch (error) {this.failure = error; throw error;}
    }
}
