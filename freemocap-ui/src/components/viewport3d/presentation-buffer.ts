/** Holds only presentation values; unexpected input loss expires, deliberate pause holds. */
export class PresentationBuffer<T> {
    private readonly values = new Map<string, {value: T; expires: number}>();
    private timer: ReturnType<typeof setTimeout> | null = null;
    private paused = false;
    constructor(private readonly publish: (values: T[]) => void, private readonly graceMs: number) {}

    setPaused(paused: boolean): void {
        if (this.paused === paused) return;
        this.paused = paused;
        // Resume gets one normal grace interval for the next camera frame to arrive.
        if (!paused) {
            const expires = performance.now() + this.graceMs;
            for (const entry of this.values.values()) entry.expires = expires;
        }
        this.flush();
    }

    /** A complete new frame supersedes even entities omitted from that frame. */
    replace(values: readonly T[], key: (value: T) => string): void {
        this.values.clear();
        this.update(values, key, () => true);
    }

    update(values: readonly T[], key: (value: T) => string, valid: (value: T) => boolean): void {
        const now = performance.now();
        for (const value of values) {
            if (valid(value)) this.values.set(key(value), {value, expires: now + this.graceMs});
        }
        this.flush();
    }

    clear(): void {
        if (this.timer !== null) clearTimeout(this.timer);
        this.timer = null;
        this.values.clear();
        this.publish([]);
    }

    private flush(): void {
        if (this.timer !== null) clearTimeout(this.timer);
        this.timer = null;
        const now = performance.now();
        let nextExpiry = Infinity;
        for (const [key, entry] of this.values) {
            if (!this.paused && entry.expires <= now) this.values.delete(key);
            else nextExpiry = Math.min(nextExpiry, entry.expires);
        }
        this.publish(Array.from(this.values.values(), entry => entry.value));
        if (!this.paused && Number.isFinite(nextExpiry)) this.timer = setTimeout(() => this.flush(), Math.max(1, nextExpiry - now));
    }
}
