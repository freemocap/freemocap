export class StartupStoppedError extends Error {
    constructor(message: string) {super(message); this.name = 'StartupStoppedError';}
}

export function isStartupStopped(error: unknown): boolean {
    return error !== null && typeof error === 'object' && 'name' in error && error.name === 'StartupStoppedError';
}

/** Only the explicit stop contract is cancellation; other 409s remain failures. */
export async function checkStartupStopped(response: Response): Promise<void> {
    if (response.status !== 409) return;
    let body: unknown;
    try {body = await response.clone().json();} catch {return;}
    if (body === null || typeof body !== 'object' || !('detail' in body)) return;
    const detail = body.detail;
    if (detail !== null && typeof detail === 'object' && 'code' in detail && detail.code === 'startup_stopped') {
        throw new StartupStoppedError('message' in detail && typeof detail.message === 'string' ? detail.message : 'Realtime startup stopped');
    }
}
