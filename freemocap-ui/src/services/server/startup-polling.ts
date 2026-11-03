import type {RealtimeStartupStatus} from '@/types/realtime-startup';

/** One bounded status read; aborting this read never cancels server startup. */
export async function readStartupWithDeadline(
    read: (signal: AbortSignal) => Promise<RealtimeStartupStatus>,
    signal: AbortSignal,
    timeoutMs = 3000,
): Promise<RealtimeStartupStatus> {
    const request = new AbortController();
    const onAbort = () => request.abort(signal.reason);
    signal.addEventListener('abort', onAbort, {once: true});
    if (signal.aborted) onAbort();
    let timeout: ReturnType<typeof setTimeout>;
    const deadline = new Promise<never>((_, reject) => {
        timeout = setTimeout(() => {
            request.abort();
            reject(new Error('The server has not answered the startup status request'));
        }, timeoutMs);
    });
    try {
        return await Promise.race([read(request.signal), deadline]);
    } finally {
        clearTimeout(timeout!);
        signal.removeEventListener('abort', onAbort);
    }
}

export function startupStillPending(snapshot: RealtimeStartupStatus): boolean {
    return snapshot.status === 'running' || snapshot.status === 'stopping';
}
