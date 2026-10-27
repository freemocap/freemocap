
import {z} from 'zod';

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
    // 'ui' for browser console logs, 'server' (default) for backend logs
    source: z.string().optional().default('server'),
});

export type LogRecord = z.infer<typeof LogRecordSchema>;

const MAX_ENTRIES = 10_000;

// Only persist the most recent 300 entries. The full 10k-entry buffer
// remains in memory for scrollback during the current renderer lifetime.
const MAX_PERSISTED_ENTRIES = 300;
const STORAGE_KEY = 'freemocap_log_store';

// Persist periodically during idle time to minimize render-thread stalls.
const AUTO_SAVE_INTERVAL_MS = 20_000;

export type LogSnapshot = {
    entries: LogRecord[];
    hasErrors: boolean;
    countsByLevel: Record<string, number>;
    version: number;
};

/**
 * Mutable store for streaming log records.
 * Components poll getSnapshot() on their own schedule.
 *
 * Persists the latest 300 entries to sessionStorage so logs survive
 * renderer refreshes (Ctrl+R), but start fresh in a new app session.
 *
 * Uses a dirty flag, version counter, and deferred periodic persistence
 * to avoid unnecessary copying and serialization.
 */
export class LogStore {
    private entries: LogRecord[] = [];
    private countsByLevel: Record<string, number> = {};
    private hasErrors: boolean = false;

    private version: number = 0;
    private lastSnapshotVersion: number = -1;

    private cachedEntries: LogRecord[] = [];
    private cachedCountsByLevel: Record<string, number> = {};

    private dirty: boolean = false;
    private saveInterval: ReturnType<typeof setInterval> | null = null;
    private idlePersistHandle: number | null = null;

    constructor() {
        this.restoreFromSessionStorage();
        this.saveInterval = setInterval(() => this.persistIfDirty(), AUTO_SAVE_INTERVAL_MS);
    }

    /** Stop auto-save and flush remaining logs. */
    dispose(): void {
        if (this.saveInterval !== null) {
            clearInterval(this.saveInterval);
            this.saveInterval = null;
        }

        if (this.idlePersistHandle !== null) {
            const cic = (globalThis as typeof globalThis & {
                cancelIdleCallback?: (handle: number) => void;
            }).cancelIdleCallback;

            if (cic) cic(this.idlePersistHandle);
            else clearTimeout(this.idlePersistHandle);

            this.idlePersistHandle = null;
        }

        this.persistToSessionStorage();
    }

    add(record: LogRecord): void {
        this.entries.push(record);
        this.version++;

        const level = record.levelname;
        this.countsByLevel[level] = (this.countsByLevel[level] || 0) + 1;

        if (level === 'ERROR' || level === 'CRITICAL') {
            this.hasErrors = true;
        }

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

        this.dirty = true;
    }

    /**
     * Return a cached snapshot, copying entries only when logs change.
     */
    getSnapshot(): LogSnapshot {
        if (this.version !== this.lastSnapshotVersion) {
            this.cachedEntries = this.entries.slice();
            this.cachedCountsByLevel = {...this.countsByLevel};
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
        this.dirty = false;
        this.version++;

        this.cachedEntries = [];
        this.cachedCountsByLevel = {};
        this.lastSnapshotVersion = this.version;

        this.clearSessionStorage();
    }

    /** Force an immediate persist (used for beforeunload). */
    persistNow(): void {
        this.persistToSessionStorage();
    }

    // ── Persistence helpers ─────────────────────────────────────────

    private persistIfDirty(): void {
        if (!this.dirty || this.idlePersistHandle !== null) return;

        const ric = (globalThis as typeof globalThis & {
            requestIdleCallback?: (cb: () => void, opts?: {timeout: number}) => number;
        }).requestIdleCallback;

        const run = (): void => {
            this.idlePersistHandle = null;
            this.persistToSessionStorage();
        };

        this.idlePersistHandle = ric
            ? ric(run, {timeout: AUTO_SAVE_INTERVAL_MS})
            : (setTimeout(run, 0) as unknown as number);
    }

    private persistToSessionStorage(): void {
        try {
            const toPersist = this.entries.length > MAX_PERSISTED_ENTRIES
                ? this.entries.slice(this.entries.length - MAX_PERSISTED_ENTRIES)
                : this.entries;

            sessionStorage.setItem(STORAGE_KEY, JSON.stringify(toPersist));
            this.dirty = false;
        } catch {
            // sessionStorage unavailable or full — ignore
        }
    }

    private restoreFromSessionStorage(): void {
        try {
            const raw = sessionStorage.getItem(STORAGE_KEY);
            if (!raw) return;

            const parsed = JSON.parse(raw);
            if (!Array.isArray(parsed) || parsed.length === 0) return;

            const restored: LogRecord[] = [];

            for (const item of parsed) {
                const result = LogRecordSchema.safeParse(item);
                if (result.success) restored.push(result.data);
            }

            if (restored.length === 0) return;

            if (restored.length > MAX_ENTRIES) {
                restored.splice(0, restored.length - MAX_ENTRIES);
            }

            this.entries = restored;

            this.countsByLevel = {};
            this.hasErrors = false;

            for (const entry of this.entries) {
                const level = entry.levelname;
                this.countsByLevel[level] = (this.countsByLevel[level] || 0) + 1;

                if (level === 'ERROR' || level === 'CRITICAL') {
                    this.hasErrors = true;
                }
            }

            this.version++;
        } catch {
            // Corrupted or unavailable storage — start fresh
        }
    }

    private clearSessionStorage(): void {
        try {
            sessionStorage.removeItem(STORAGE_KEY);
        } catch {
            // ignore
        }
    }
}
