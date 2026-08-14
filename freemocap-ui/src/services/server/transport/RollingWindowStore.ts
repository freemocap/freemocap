// RollingWindowStore.ts
//
// Generic fixed-capacity ring buffer. Each push appends one frame; when over
// maxFrames the oldest frame is evicted. Subscribers fire on every push.
// Memory is bounded by construction — old frames are overwritten in place.

export interface RollingWindowConfig {
  /** Maximum frames retained. Default 100. */
  maxFrames: number;
  /** Optional — evict frames older than this many ms (null = no age limit). */
  maxAgeMs?: number | null;
}

export class RollingWindowStore<T> {
  private readonly maxFrames: number;
  private readonly maxAgeMs: number | null;
  private readonly frames: { frame: T; atMs: number }[] = [];
  private readonly subscribers = new Set<(frame: T) => void>();

  constructor(config: RollingWindowConfig) {
    this.maxFrames = config.maxFrames > 0 ? config.maxFrames : 100;
    this.maxAgeMs = config.maxAgeMs ?? null;
  }

  /** Push one frame's data. Oldest frame is evicted if over maxFrames. */
  push(frame: T): void {
    const atMs = Date.now();
    this.frames.push({ frame, atMs });
    this.evict(atMs);
    for (const cb of this.subscribers) cb(frame);
  }

  /** Get the last N frames (most recent first). Default: all in window. */
  getLast(n?: number): T[] {
    const count = n === undefined ? this.frames.length : Math.min(n, this.frames.length);
    const out: T[] = [];
    for (let i = this.frames.length - count; i < this.frames.length; i++) {
      out.push(this.frames[i].frame);
    }
    return out; // already chronological (oldest of the window first); caller may reverse
  }

  /** The most recent frame, or null if empty. */
  getLatest(): T | null {
    return this.frames.length === 0 ? null : this.frames[this.frames.length - 1].frame;
  }

  /** Subscribe to every push. Returns an unsubscribe function. */
  subscribe(cb: (frame: T) => void): () => void {
    this.subscribers.add(cb);
    return () => {
      this.subscribers.delete(cb);
    };
  }

  /** Number of frames currently retained. */
  get length(): number {
    return this.frames.length;
  }

  /** Drop all frames. */
  clear(): void {
    this.frames.length = 0;
  }

  private evict(nowMs: number): void {
    if (this.maxAgeMs !== null) {
      const cutoff = nowMs - this.maxAgeMs;
      let i = 0;
      while (i < this.frames.length && this.frames[i].atMs < cutoff) i++;
      if (i > 0) this.frames.splice(0, i);
    }
    while (this.frames.length > this.maxFrames) {
      this.frames.shift();
    }
  }
}
