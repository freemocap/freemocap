import {serverClient} from './sdk';
import {OnnxPreparationSchema, type OnnxPreparation} from '@/types/onnx-preparation';
import {StartupStatusUnavailableError} from './realtime-startup';
import {getDetailedErrorMessage} from '@/store/slices/thunk-helpers';

export type PreparationAction = 'status' | 'prepare' | 'stop';

export class PreparationPipelineUnavailableError extends Error {}

/** A stale pipeline is terminal until a different pipeline/server or reconnect. */
export class PreparationPipelineAvailability {
    private unavailable: {identity: string; pipelineId: string; message: string} | null = null;
    reason(identity: string, pipelineId: string): string | null {
        return this.unavailable?.identity === identity && this.unavailable.pipelineId === pipelineId ? this.unavailable.message : null;
    }
    markUnavailable(identity: string, pipelineId: string, message: string): void {
        this.unavailable = {identity, pipelineId, message};
    }
    reset(): void {this.unavailable = null;}
}

/** The generated SDK owns paths and serialization for explicit preparation. */
export async function requestOnnxPreparation(pipelineId: string, action: PreparationAction, signal: AbortSignal): Promise<OnnxPreparation> {
    const options = {path: {pipeline_id: pipelineId}, signal};
    const responses = serverClient().responses;
    const response = await (action === 'status' ? responses.onnx_preparation_status(options)
        : action === 'prepare' ? responses.prepare_onnx(options) : responses.stop_onnx_preparation(options));
    if (response.status === 404) throw new StartupStatusUnavailableError();
    if (response.status === 409 && action === 'status') throw new PreparationPipelineUnavailableError(await getDetailedErrorMessage(response));
    if (!response.ok) throw new Error(await getDetailedErrorMessage(response));
    return OnnxPreparationSchema.parse(await response.json());
}

export async function boundedPreparationRequest(pipelineId: string, action: PreparationAction, owner: AbortSignal, timeoutMs = 3000): Promise<OnnxPreparation> {
    const controller = new AbortController();
    const abort = () => controller.abort(owner.reason);
    owner.addEventListener('abort', abort, {once: true});
    if (owner.aborted) abort();
    let timer: ReturnType<typeof setTimeout>;
    try {
        return await Promise.race([requestOnnxPreparation(pipelineId, action, controller.signal), new Promise<never>((_, reject) => {
            timer = setTimeout(() => {controller.abort(); reject(new Error('The server has not answered the TensorRT preparation request'));}, timeoutMs);
        })]);
    } finally {clearTimeout(timer!); owner.removeEventListener('abort', abort);}
}

export function preparationWorking(snapshot: OnnxPreparation): boolean {
    return ['queued', 'running', 'stopping', 'ready'].includes(snapshot.status);
}
