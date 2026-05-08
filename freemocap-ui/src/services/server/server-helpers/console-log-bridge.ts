// src/services/server/server-helpers/console-log-bridge.ts
//
// Mirrors browser console output (and unhandled errors) into the LogStore so
// the in-app LogTerminal shows the same messages a developer would see in
// DevTools. The original console methods are still invoked, so DevTools is
// unaffected.

import {LogRecord, LogStore} from './log-store';

type ConsoleMethod = 'log' | 'info' | 'warn' | 'error' | 'debug';

const METHOD_LEVELS: Record<ConsoleMethod, string> = {
    log: 'INFO',
    info: 'INFO',
    warn: 'WARNING',
    error: 'ERROR',
    debug: 'DEBUG',
};

const UI_LOGGER_NAME = 'ui-console';
const BRIDGE_FILE_MARKER = 'console-log-bridge';

let installed = false;
let installedCleanup: (() => void) | null = null;

interface CallerInfo {
    funcName: string;
    pathname: string;
    filename: string;
    module: string;
    lineno: number;
}

/** Walk the V8/SpiderMonkey stack to find the first frame outside this bridge file. */
function extractCallerInfo(): CallerInfo {
    const stack = new Error().stack ?? '';
    for (const line of stack.split('\n')) {
        const trimmed = line.trim();
        if (!trimmed.startsWith('at ')) continue;
        if (trimmed.includes(BRIDGE_FILE_MARKER)) continue;
        // Format: "at FuncName (path/file.ts:line:col)" or "at path/file.ts:line:col"
        const match = trimmed.match(/at (?:(.+?) \()?(.+?):(\d+):\d+\)?/);
        if (match) {
            const funcName = match[1]?.trim() || '';
            const pathname = match[2] || 'browser';
            const lineno = parseInt(match[3], 10) || 0;
            const filename = pathname.split('/').pop() || pathname;
            const mod = filename.replace(/\.[^.]+$/, '');
            return {funcName, pathname, filename, module: mod, lineno};
        }
    }
    return {funcName: '', pathname: 'browser', filename: 'browser', module: 'browser', lineno: 0};
}

function formatArg(arg: unknown): string {
    if (typeof arg === 'string') return arg;
    if (arg instanceof Error) return arg.stack ?? `${arg.name}: ${arg.message}`;
    if (arg === null || arg === undefined) return String(arg);
    if (typeof arg === 'object') {
        try {
            return JSON.stringify(arg);
        } catch {
            return String(arg);
        }
    }
    return String(arg);
}

function buildUiConsoleRecord(
    levelname: string,
    args: unknown[],
    caller: CallerInfo,
    stackInfo: string | null = null,
): LogRecord {
    const message = args.map(formatArg).join(' ');
    const now = Date.now();
    const date = new Date(now);
    // HH:MM:SS,mmm — close to Python logging's default asctime
    const pad = (n: number, w = 2): string => String(n).padStart(w, '0');
    const asctime =
        `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ` +
        `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())},` +
        `${pad(date.getMilliseconds(), 3)}`;

    const levelno =
        levelname === 'DEBUG' ? 10 :
        levelname === 'INFO' ? 20 :
        levelname === 'WARNING' ? 30 :
        levelname === 'ERROR' ? 40 :
        levelname === 'CRITICAL' ? 50 : 20;

    return {
        name: UI_LOGGER_NAME,
        msg: message,
        args: [],
        levelname,
        levelno,
        pathname: caller.pathname,
        filename: caller.filename,
        module: caller.module,
        exc_info: null,
        exc_text: null,
        stack_info: stackInfo,
        lineno: caller.lineno,
        funcName: caller.funcName,
        created: now / 1000,
        msecs: date.getMilliseconds(),
        relativeCreated: 0,
        thread: 0,
        threadName: 'main',
        processName: 'ui',
        process: 0,
        delta_t: '',
        message,
        asctime,
        formatted_message: `${asctime} [${UI_LOGGER_NAME}] ${levelname} - ${message}`,
        type: 'log_record',
        source: 'ui',
    };
}

/**
 * Wraps console.{log,info,warn,error,debug} so each call also appends a
 * LogRecord to the given store. Also captures `error` and
 * `unhandledrejection` window events as ERROR records.
 *
 * Idempotent: subsequent calls are no-ops and return the same cleanup. This
 * keeps things sane under React StrictMode's double-invoked effects.
 *
 * Returns a cleanup function that restores the original console methods and
 * removes the global error listeners.
 */
export function installConsoleLogBridge(store: LogStore): () => void {
    if (installed && installedCleanup) {
        return installedCleanup;
    }

    const originals: Partial<Record<ConsoleMethod, (...args: unknown[]) => void>> = {};

    (Object.keys(METHOD_LEVELS) as ConsoleMethod[]).forEach((method) => {
        const original = console[method].bind(console);
        originals[method] = original;
        console[method] = (...args: unknown[]): void => {
            original(...args);
            try {
                const caller = extractCallerInfo();
                store.add(buildUiConsoleRecord(METHOD_LEVELS[method], args, caller));
            } catch {
                // Never let logging blow up the caller.
            }
        };
    });

    const onError = (event: ErrorEvent): void => {
        const err = event.error;
        const stack = err instanceof Error ? (err.stack ?? null) : null;
        const msg = err instanceof Error
            ? `${err.name}: ${err.message}`
            : (event.message || 'Uncaught error');
        try {
            store.add(buildUiConsoleRecord('ERROR', [msg], extractCallerInfo(), stack));
        } catch { /* ignore */ }
    };

    const onUnhandledRejection = (event: PromiseRejectionEvent): void => {
        const reason = event.reason;
        const stack = reason instanceof Error ? (reason.stack ?? null) : null;
        const msg = reason instanceof Error
            ? `Unhandled promise rejection: ${reason.name}: ${reason.message}`
            : `Unhandled promise rejection: ${formatArg(reason)}`;
        try {
            store.add(buildUiConsoleRecord('ERROR', [msg], extractCallerInfo(), stack));
        } catch { /* ignore */ }
    };

    window.addEventListener('error', onError);
    window.addEventListener('unhandledrejection', onUnhandledRejection);

    installed = true;
    installedCleanup = (): void => {
        (Object.keys(originals) as ConsoleMethod[]).forEach((method) => {
            const original = originals[method];
            if (original) {
                console[method] = original;
            }
        });
        window.removeEventListener('error', onError);
        window.removeEventListener('unhandledrejection', onUnhandledRejection);
        installed = false;
        installedCleanup = null;
    };
    return installedCleanup;
}
