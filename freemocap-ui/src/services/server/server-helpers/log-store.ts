// src/services/server/server-helpers/log-store.ts

import { z } from 'zod';

export const LogRecordSchema = z.object({
    name: z.string(),
    msg: z.string().nullable().default(""),
    args: z.array(z.any()),
    levelname: z.string(),
    levelno: z.number(),
    pathname: z.string(),
    filename: z.string(),
    module: z.string(),
    exc_info: z.string().nullable(),
    exc_text: z.string().nullable(),
    stack_info: z.string().nullable(),
    lineno: z.number(),
    funcName: z.string(),
    created: z.number(),
    msecs: z.number(),
    relativeCreated: z.number(),
    thread: z.number(),
    threadName: z.string(),
    processName: z.string(),
    process: z.number(),
    delta_t: z.string(),
    message: z.string(),
    asctime: z.string(),
    formatted_message: z.string(),
    type: z.string(),
});

export type LogRecord = z.infer<typeof LogRecordSchema>;

const MAX_ENTRIES = 1000;

export type LogSnapshot = {
    entries: LogRecord[];
    hasErrors: boolean;
    countsByLevel: Record<string, number>;
    version: number;
};

/**
 * Mutable store for streaming log records from the backend.
 * Lives in a ref — no Redux, no immutable copies, no re-renders on every message.
 * Components poll via getSnapshot() on their own schedule (typically ~500ms).
 *
 * Uses a version counter to avoid copying the entries array when nothing has
 * changed since the last snapshot. The snapshot's entries array is only
 * reallocated when new logs have arrived.
 */
export class LogStore {
    private entries: LogRecord[] = [];
    private countsByLevel: Record<string, number> = {};
    private hasErrors: boolean = false;

    /** Incremented on every mutation (add / clear). */
    private version: number = 0;

    /** Version at which the last snapshot was taken. */
    private lastSnapshotVersion: number = -1;

    /** Cached snapshot entries — reused when version hasn't changed. */
    private cachedEntries: LogRecord[] = [];
    private cachedCountsByLevel: Record<string, number> = {};

    add(record: LogRecord): void {
        this.entries.push(record);
        this.version++;

        // Update counts
        const level = record.levelname;
        this.countsByLevel[level] = (this.countsByLevel[level] || 0) + 1;

        // Track error state
        if (level === 'ERROR' || level === 'CRITICAL') {
            this.hasErrors = true;
        }

        // Trim to capacity
        if (this.entries.length > MAX_ENTRIES) {
            const removed = this.entries.splice(0, this.entries.length - MAX_ENTRIES);
            for (const r of removed) {
                this.countsByLevel[r.levelname]--;
                if (this.countsByLevel[r.levelname] <= 0) {
                    delete this.countsByLevel[r.levelname];
                }
            }
            this.hasErrors = (this.countsByLevel['ERROR'] ?? 0) > 0
                || (this.countsByLevel['CRITICAL'] ?? 0) > 0;
        }
    }

    /**
     * Returns a snapshot for React components to read during render.
     * Only copies the entries array when new logs have arrived since the
     * last call, avoiding the per-poll GC pressure of unconditional .slice().
     */
    getSnapshot(): LogSnapshot {
        if (this.version !== this.lastSnapshotVersion) {
            this.cachedEntries = this.entries.slice();
            this.cachedCountsByLevel = { ...this.countsByLevel };
            this.lastSnapshotVersion = this.version;
        }

        return {
            entries: this.cachedEntries,
            hasErrors: this.hasErrors,
            countsByLevel: this.cachedCountsByLevel,
            version: this.version,
        };
    }

    clear(): void {
        this.entries = [];
        this.countsByLevel = {};
        this.hasErrors = false;
        this.version++;
        this.cachedEntries = [];
        this.cachedCountsByLevel = {};
        this.lastSnapshotVersion = this.version;
    }
}
