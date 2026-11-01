import {serverUrls} from '@/constants/server-urls';
import {recordingLocationFromPath} from './recording-location';
import {getDetailedErrorMessage} from '@/store/slices/thunk-helpers';

export function recordingExportUrl(path: string, resource: '/exports' | '/export-options'): string {
    const location = recordingLocationFromPath(path);
    return serverUrls.recordingResource(location.recordingId, resource, location.recordingParentDirectory);
}

export async function createRecordingExport(path: string, options: object, signal?: AbortSignal): Promise<{task_id: string}> {
    const response = await fetch(recordingExportUrl(path, '/exports'), {
        method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(options), signal,
    });
    if (!response.ok) throw new Error(await getDetailedErrorMessage(response));
    return response.json();
}

/** Aborting observation does not silently cancel work on the server. */
export async function waitForTaskResult<T>(taskId: string, signal?: AbortSignal): Promise<T> {
    for (;;) {
        signal?.throwIfAborted();
        const response = await fetch(`${serverUrls.getHttpUrl()}/freemocap/tasks/${encodeURIComponent(taskId)}`, {signal});
        if (!response.ok) throw new Error(await getDetailedErrorMessage(response));
        const task = await response.json();
        if (task.status === 'complete') {
            if (task.result === null || task.result === undefined) throw new Error('Task completed without an export result');
            return task.result as T;
        }
        if (task.status === 'failed' || task.status === 'cancelled') throw new Error(task.error ?? task.progress.detail);
        if (task.status !== 'queued' && task.status !== 'running') throw new Error(`Unknown task status: ${task.status}`);
        await new Promise<void>((resolve, reject) => {
            const abort = () => {clearTimeout(timer); reject(signal?.reason);};
            const timer = setTimeout(() => {signal?.removeEventListener('abort', abort); resolve();}, 500);
            signal?.addEventListener('abort', abort, {once: true});
        });
    }
}
