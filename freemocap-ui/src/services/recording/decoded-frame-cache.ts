/** Per-media cache. Owns images; callers borrow them until eviction or clear.
 * The RGBA byte estimate excludes browser/GPU overhead and is not a process-memory limit.
 */
export class DecodedFrameCache {
    private readonly frames = new Map<number, ImageBitmap>();
    private bytes = 0;

    constructor(private readonly budgetBytes: number) {
        if (!Number.isSafeInteger(budgetBytes) || budgetBytes <= 0) {
            throw new Error('Decoded frame cache requires a positive byte budget');
        }
    }

    get sizeBytes(): number { return this.bytes; }

    get(frameNumber: number): ImageBitmap | undefined {
        const frame = this.frames.get(frameNumber);
        if (frame) {
            this.frames.delete(frameNumber);
            this.frames.set(frameNumber, frame);
        }
        return frame;
    }

    /** Takes ownership even when the image exceeds the budget and cannot be retained. */
    put(frameNumber: number, frame: ImageBitmap): void {
        if (!Number.isSafeInteger(frameNumber) || frameNumber < 0) {
            frame.close();
            throw new Error('Decoded frame ordinal must be a nonnegative integer');
        }
        const cost = frame.width * frame.height * 4;
        if (!cost) {
            frame.close();
            throw new Error('Cannot cache an empty or closed image');
        }
        this.remove(frameNumber);
        if (cost > this.budgetBytes) { frame.close(); return; }
        while (this.bytes + cost > this.budgetBytes) {
            const oldest = this.frames.keys().next();
            if (oldest.done) throw new Error('Decoded cache accounting is inconsistent');
            this.remove(oldest.value);
        }
        this.frames.set(frameNumber, frame);
        this.bytes += cost;
    }

    clear(): void {
        for (const ordinal of this.frames.keys()) this.remove(ordinal);
    }

    private remove(ordinal: number): void {
        const frame = this.frames.get(ordinal);
        if (!frame) return;
        this.bytes -= frame.width * frame.height * 4;
        this.frames.delete(ordinal);
        frame.close();
    }
}
