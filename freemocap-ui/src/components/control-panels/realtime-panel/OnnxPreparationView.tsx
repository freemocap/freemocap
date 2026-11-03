import type {OnnxPreparation} from '@/types/onnx-preparation';
import {startupElapsed} from './RealtimeStartupStatusView';

const headings: Record<OnnxPreparation['status'], string> = {
    unavailable: 'TensorRT preparation unavailable', idle: 'TensorRT preparation',
    queued: 'TensorRT preparation queued', running: 'Preparing TensorRT',
    stopping: 'Stopping TensorRT preparation', ready: 'TensorRT prepared; waiting for activation',
    activated: 'TensorRT preparation activated', failed: 'TensorRT preparation failed',
    cancelled: 'TensorRT preparation stopped',
};

export function OnnxPreparationView({snapshot, error, unavailable = false, busy = false, onPrepare, onStop}: {
    snapshot: OnnxPreparation | null; error?: string | null; unavailable?: boolean; busy?: boolean;
    onPrepare?: () => void; onStop?: () => void;
}) {
    if (unavailable) return <aside role="status" className="text sm p-1">TensorRT preparation unavailable from this server version.</aside>;
    if (!snapshot && !error) return null;
    return <section aria-label="TensorRT preparation" className="bg-middark border-1 br-2 p-2 flex flex-col gap-1 text text-white">
        {snapshot && <>
            <p role="status" className="text-bold">{headings[snapshot.status]}</p>
            <p className="text sm">Requested provider: {snapshot.requested_provider ?? 'Auto'} · Active provider: {snapshot.active_provider ?? 'Not reported'}</p>
            <p className="text sm">{snapshot.phase.replaceAll('_', ' ')} · Elapsed: {startupElapsed(snapshot.elapsed_seconds)}{snapshot.model_name && <> · Model: {snapshot.model_name}</>}</p>
            {snapshot.message && <p className="text sm">{snapshot.message}</p>}
            {snapshot.error && <p role="alert" className="text sm text-error">{snapshot.error}</p>}
            {(snapshot.can_prepare || snapshot.can_cancel) && <p className="text sm">TensorRT preparation uses the GPU and may reduce live FPS. Preparation starts only when you request it.</p>}
            {snapshot.status === 'stopping' && <p className="text sm">Waiting for the preparation worker to exit and release its resources.</p>}
            <div className="flex flex-row gap-1">
                {snapshot.can_prepare && onPrepare && <button type="button" className="button sm" disabled={busy} onClick={onPrepare}>{snapshot.status === 'failed' || snapshot.status === 'cancelled' ? 'Retry TensorRT preparation' : 'Prepare TensorRT'}</button>}
                {snapshot.can_cancel && snapshot.status !== 'activated' && onStop && <button type="button" className="button sm" disabled={busy || snapshot.status === 'stopping'} onClick={onStop}>Stop preparation; keep CUDA</button>}
            </div>
        </>}
        {error && <p role="alert" className="text sm text-error">{error}. The last reported preparation state may be out of date.</p>}
    </section>;
}
