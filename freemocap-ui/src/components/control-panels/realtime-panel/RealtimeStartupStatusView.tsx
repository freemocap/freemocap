import type {RealtimeStartupStatus} from '@/types/realtime-startup';

const phaseLabels: Record<string, string> = {
    starting: 'Starting realtime processing',
    starting_cameras: 'Starting cameras',
    starting_pipeline: 'Starting the processing pipeline',
    updating_pipeline: 'Applying processing settings',
    loading_models: 'Loading tracking models',
    warming_models: 'Warming up tracking models',
    waiting_for_frames: 'Waiting for the first processed frame',
    running: 'Starting realtime processing',
};

export function startupElapsed(seconds: number): string {
    const wholeSeconds = Math.floor(seconds);
    if (wholeSeconds < 60) return `${wholeSeconds}s`;
    return `${Math.floor(wholeSeconds / 60)}m ${String(wholeSeconds % 60).padStart(2, '0')}s`;
}

interface Props {
    snapshot: RealtimeStartupStatus | null;
    statusError?: string | null;
    pending?: boolean;
    statusUnavailable?: boolean;
    onStop?: () => void;
    onRetry?: () => void;
    /** Only supplied when the backend can safely continue with its default. */
    onContinueWithDefault?: () => void;
}

/** Presentation only: controllers own polling and determine available actions. */
export function RealtimeStartupStatusView({snapshot, statusError, pending = false, statusUnavailable = false, onStop, onRetry, onContinueWithDefault}: Props) {
    if (statusUnavailable) return <aside role="status" className="text sm p-1">
        Startup status unavailable from this server version.
    </aside>;
    if ((!snapshot || snapshot.status === 'idle') && !statusError && !pending) return null;
    const status = snapshot?.status;
    const heading = status === 'ready' ? 'Realtime processing is ready'
        : status === 'failed' ? 'Realtime startup failed'
        : status === 'stopped' ? 'Realtime startup stopped'
        : status === 'stopping' ? 'Stopping realtime startup'
        : snapshot ? phaseLabels[snapshot.phase] ?? 'Starting realtime processing'
        : 'Checking realtime startup';
    const isPending = status === 'running' || status === 'stopping';
    return <section aria-label="Realtime startup" className="bg-middark border-1 br-2 p-2 flex flex-col gap-1 text text-white">
        <div role={status === 'failed' ? 'alert' : 'status'} aria-live="polite">
            <p className="text-bold">{status === 'running' && snapshot?.preview_ready ? 'Processing: ' : ''}{heading}</p>
            {snapshot?.preview_ready && <p className="text sm">Camera preview has started</p>}
            {snapshot && <p className="text sm">Elapsed: {startupElapsed(snapshot.elapsed_seconds)}
                {isPending && <> · Current step: {startupElapsed(snapshot.phase_elapsed_seconds)}</>}</p>}
            {snapshot?.message && <p className="text sm">{snapshot.message}</p>}
            {status === 'running' && <p className="text sm">Camera preview and motion processing start separately. Camera images can appear while tracking models load; processing is ready after the first processed frame arrives.</p>}
            {snapshot?.error && <p className="text sm text-error" style={{overflowWrap: 'anywhere'}}>{snapshot.error}</p>}
            {status === 'running' && (snapshot?.delayed || (snapshot?.phase_elapsed_seconds ?? 0) >= 15) &&
                <p className="text sm">This step is still running. No completion estimate is available.</p>}
            {status === 'stopping' && <p className="text sm">Stop has been requested. The current operation must finish before its resources can be released.</p>}
            {status === 'ready' && <p className="text sm">The first processed frame has arrived.</p>}
        </div>
        {statusError && <p role="alert" className="text sm text-error" style={{overflowWrap: 'anywhere'}}>
            Could not refresh startup status: {statusError}. The last reported phase may be out of date.
        </p>}
        <div className="flex flex-row gap-1">
            {status === 'running' && onStop && <button type="button" className="button sm" onClick={onStop}>Stop startup</button>}
            {status === 'stopping' && <button type="button" className="button sm" disabled>Stop requested</button>}
            {(status === 'failed' || status === 'stopped') && onRetry && <button type="button" className="button sm" onClick={onRetry}>Retry startup</button>}
            {status === 'running' && onContinueWithDefault && <button type="button" className="button sm" onClick={onContinueWithDefault}>Continue with default processing</button>}
        </div>
    </section>;
}
