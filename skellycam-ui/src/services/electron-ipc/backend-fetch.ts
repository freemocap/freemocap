/**
 * backendFetch — drop-in replacement for fetch() when calling the Python backend.
 *
 * In Electron production builds the renderer loads from file://, making requests
 * to localhost:53117 cross-origin. Chromium's cross-origin connection pool fills up
 * with stalled requests and new ones never get a socket slot.
 *
 * This routes all backend HTTP calls through the Electron main process via IPC,
 * using net.fetch() which has no connection-pool or CORS restrictions.
 * Falls back to native fetch() in non-Electron contexts (plain browser).
 */
import { electronIpcClient } from '@/services/electron-ipc/electron-ipc-client';

interface BackendResponse {
    ok: boolean;
    status: number;
    statusText: string;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    json(): Promise<any>;
    text(): Promise<string>;
}

export async function backendFetch(url: string, init?: RequestInit): Promise<BackendResponse> {
    // Check at call time so we always reflect the actual Electron environment state.
    if (typeof window !== 'undefined' && window.electronAPI) {
        const method = (init?.method ?? 'GET').toUpperCase();
        const headers = init?.headers as Record<string, string> | undefined;
        const body = typeof init?.body === 'string' ? init.body : undefined;

        const result = await electronIpcClient.backendHttp.fetch.mutate({ url, method, headers, body });

        return {
            ok: result.ok,
            status: result.status,
            statusText: result.statusText,
            json: async () => JSON.parse(result.data),
            text: async () => result.data,
        };
    }

    // Non-Electron fallback (plain browser dev without proxy)
    return fetch(url, init);
}
