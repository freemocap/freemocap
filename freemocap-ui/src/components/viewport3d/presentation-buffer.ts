/** Holds only presentation values; expiry is driven even when input stops. */
export class PresentationBuffer<T> {
    private readonly values = new Map<string, {value: T; expires: number}>();
    private timer: ReturnType<typeof setTimeout> | null = null;
    constructor(private readonly publish: (values: T[]) => void, private readonly graceMs: number) {}

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
            if (entry.expires <= now) this.values.delete(key);
            else nextExpiry = Math.min(nextExpiry, entry.expires);
        }
        this.publish(Array.from(this.values.values(), entry => entry.value));
        if (Number.isFinite(nextExpiry)) this.timer = setTimeout(() => this.flush(), Math.max(1, nextExpiry - now));
    }
}
