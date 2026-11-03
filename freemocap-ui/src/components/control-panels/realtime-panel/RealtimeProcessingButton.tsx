import {useEffect, useRef} from 'react';
import {useRealtimeStartup} from '@/hooks/useRealtimeStartup';
import {useAppDispatch} from '@/store/hooks';
import {pipelineErrorReceived} from '@/store/slices/realtime/realtime-slice';

const stages: Record<string, string> = {
    starting_cameras: 'Starting cameras', starting_pipeline: 'Starting processing',
    updating_pipeline: 'Updating processing', loading_models: 'Loading tracking',
    warming_models: 'Warming tracking', waiting_for_frames: 'Waiting for frames',
};

/** One control for processing start, observed startup, cancellation and retry. */
export function RealtimeProcessingButton({connected, loading, onToggle}: {
    connected: boolean; loading: boolean; onToggle: () => void;
}) {
    const startup = useRealtimeStartup();
    const dispatch = useAppDispatch();
    const reported = useRef<string | null>(null);
    const error = startup.statusError ?? startup.snapshot?.error ?? null;
    useEffect(() => {
        if (!error) {reported.current = null; return;}
        const key = `${startup.operationId ?? 'initial'}:${error}`;
        if (reported.current === key) return;
        reported.current = key;
        dispatch(pipelineErrorReceived(error));
    }, [dispatch, error, startup.operationId]);
    const status = startup.snapshot?.status;
    const stopping = status === 'stopping';
    const retry = !startup.pending && (status === 'failed' || status === 'stopped');
    const starting = !retry && (startup.pending || status === 'running');
    const busy = stopping || starting || loading;
    const running = connected && !busy && !retry;
    const label = stopping ? 'Stopping processing' : retry ? 'Retry realtime processing'
        : starting ? stages[startup.snapshot?.phase ?? ''] ?? 'Starting processing'
        : loading ? 'Stopping processing' : 'Realtime processing';
    const action = stopping ? undefined : retry ? startup.retry : starting ? startup.stop : loading ? undefined : onToggle;
    const actionLabel = stopping || (loading && !starting) ? 'Stopping realtime processing'
        : retry ? 'Retry realtime processing' : starting ? `Stop realtime startup: ${label}`
        : running ? 'Stop realtime processing' : 'Start realtime processing';
    return <button type="button" className={`button sm br-1 flex items-center gap-1 ${running ? 'activated' : 'secondary'}`}
        style={{border: '1px solid var(--color-border-control)'}}
        aria-label={actionLabel} title={actionLabel} aria-pressed={running} aria-busy={busy}
        disabled={!action} onClick={action}>
        <span aria-hidden className={`icon icon-size-20 ${busy ? 'loader-icon' : running ? 'live-active-icon' : 'live-icon'}`}/>
        <p className="text sm" style={{whiteSpace: 'nowrap'}}>{label}</p>
    </button>;
}
