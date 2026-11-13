import {useRealtimeStartup} from '@/hooks/useRealtimeStartup';

/** Stable toggle. Only current activity and an outstanding request affect its operation. */
export function RealtimeProcessingButton({connected, loading, onToggle}: {
    connected: boolean; loading: boolean; onToggle: () => void;
}) {
    const startup = useRealtimeStartup();
    const busy = loading || startup.pending;
    return <button type="button" className={`button sm br-1 flex items-center gap-1 ${connected ? 'activated' : 'secondary'}`}
        style={{border: '1px solid var(--color-border-control)'}}
        aria-label="Real-time processing" title="Real-time processing" aria-pressed={connected} aria-busy={busy}
        onClick={startup.pending ? startup.stop : onToggle}>
        <span aria-hidden className={`icon icon-size-20 ${busy ? 'loader-icon' : connected ? 'live-active-icon' : 'live-icon'}`}/>
        <p className="text sm" style={{whiteSpace: 'nowrap'}}>Real-time processing</p>
    </button>;
}
