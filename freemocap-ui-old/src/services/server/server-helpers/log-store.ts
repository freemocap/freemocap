// src/services/server/server-helpers/log-store.ts

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
const STORAGE_KEY = 'freemocap_log_store';
const AUTO_SAVE_INTERVAL_MS = 5_000;

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
 *
 * Persists log entries to localStorage so logs survive page refreshes / app
 * restarts. A divider entry is inserted on each mount to visually separate
 * sessions. Persistence uses a dirty flag + periodic save to avoid serializing
 * the full entries array on every incoming log message.
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

    /** Set when entries change since the last persist. */
    private dirty: boolean = false;

    /** Periodic save timer handle. */
    private saveInterval: ReturnType<typeof setInterval> | null = null;

    constructor() {
        this.restoreFromLocalStorage();
        this.saveInterval = setInterval(() => this.persistIfDirty(), AUTO_SAVE_INTERVAL_MS);
    }

    /** Stop the auto-save timer and flush one last time. Call on teardown. */
    dispose(): void {
        if (this.saveInterval !== null) {
            clearInterval(this.saveInterval);
            this.saveInterval = null;
        }
        this.persistToLocalStorage();
    }

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

        this.dirty = true;
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
        this.dirty = false;
        this.version++;
        this.cachedEntries = [];
        this.cachedCountsByLevel = {};
        this.lastSnapshotVersion = this.version;
        this.clearLocalStorage();
    }

    /** Force an immediate persist (used for beforeunload). */
    persistNow(): void {
        this.persistToLocalStorage();
    }

    // ── private persistence helpers ──────────────────────────────────────

    private persistIfDirty(): void {
        if (this.dirty) {
            this.persistToLocalStorage();
        }
    }

    private persistToLocalStorage(): void {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(this.entries));
            this.dirty = false;
        } catch {
            // localStorage full or unavailable — silently ignore
        }
    }

    private restoreFromLocalStorage(): void {
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            if (!raw) return;

            const parsed = JSON.parse(raw);
            if (!Array.isArray(parsed) || parsed.length === 0) return;

            // Validate each entry (schema-safe against future changes)
            const restored: LogRecord[] = [];
            for (const item of parsed) {
                const result = LogRecordSchema.safeParse(item);
                if (result.success) {
                    restored.push(result.data);
                }
            }

            if (restored.length === 0) return;

            // Truncate to capacity, leaving room for the divider + new logs
            if (restored.length >= MAX_ENTRIES) {
                restored.splice(0, restored.length - MAX_ENTRIES + 1);
            }

            this.entries = restored;

            // Recalculate aggregate state from restored entries
            this.countsByLevel = {};
            this.hasErrors = false;
            for (const entry of this.entries) {
                if (entry.type === 'divider') continue;
                const lvl = entry.levelname;
                this.countsByLevel[lvl] = (this.countsByLevel[lvl] || 0) + 1;
                if (lvl === 'ERROR' || lvl === 'CRITICAL') {
                    this.hasErrors = true;
                }
            }

            this.addDivider();
            this.version++;
        } catch {
            // Corrupted data — start fresh
        }
    }

    private addDivider(): void {
        const now = new Date();
        const divider: LogRecord = {
            name: '',
            msg: '',
            args: [],
            levelname: 'DIVIDER',
            levelno: -1,
            pathname: '',
            filename: '',
            module: '',
            exc_info: null,
            exc_text: null,
            stack_info: null,
            lineno: 0,
            funcName: '',
            created: now.getTime() / 1000,
            msecs: now.getMilliseconds(),
            relativeCreated: 0,
            thread: 0,
            threadName: '',
            processName: '',
            process: 0,
            delta_t: '',
            message: '────── App restarted ──────',
            asctime: now.toLocaleString(),
            formatted_message: '',
            type: 'divider',
            source: 'system',
        };
        this.entries.push(divider);
        this.dirty = true;
    }

    private clearLocalStorage(): void {
        try {
            localStorage.removeItem(STORAGE_KEY);
        } catch {
            // ignore
        }
    }
}
