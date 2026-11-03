import {useRealtimeStartup} from '@/hooks/useRealtimeStartup';
import {RealtimeStartupStatusView} from '@/components/control-panels/realtime-panel/RealtimeStartupStatusView';
import {useEffect, useLayoutEffect, useRef, useState} from 'react';
import {createPortal} from 'react-dom';
import './realtime-processing-control.css';

export function RealtimeStartupBanner() {
    const startup = useRealtimeStartup();
    const [open, setOpen] = useState(false);
    const [position, setPosition] = useState({top: 0, left: 0});
    const trigger = useRef<HTMLButtonElement>(null);
    const panel = useRef<HTMLDivElement>(null);
    const close = () => {setOpen(false); trigger.current?.focus();};
    useLayoutEffect(() => {
        if (!open) return;
        const place = () => {
            const box = trigger.current?.getBoundingClientRect();
            if (!box) return;
            const width = Math.min(380, window.innerWidth - 24);
            setPosition({left: Math.max(12, Math.min(box.right - width, window.innerWidth - width - 12)), top: Math.min(box.bottom + 8, window.innerHeight - 100)});
        };
        place(); window.addEventListener('resize', place);
        return () => window.removeEventListener('resize', place);
    }, [open]);
    useEffect(() => {
        if (!open) return;
        panel.current?.focus();
        const escape = (event: KeyboardEvent) => {if (event.key === 'Escape') close();};
        const outside = (event: MouseEvent) => {
            if (!panel.current?.contains(event.target as Node) && !trigger.current?.contains(event.target as Node)) setOpen(false);
        };
        window.addEventListener('keydown', escape); document.addEventListener('mousedown', outside);
        return () => {window.removeEventListener('keydown', escape); document.removeEventListener('mousedown', outside);};
    }, [open]);
    const starting = startup.pending || startup.snapshot?.status === 'running' || startup.snapshot?.status === 'stopping';
    const failed = startup.snapshot?.status === 'failed' || Boolean(startup.statusError);
    const label = starting ? 'Starting…' : failed ? 'Needs attention' : 'Processing';
    return <>
        <button ref={trigger} type="button" aria-label="Processing status" aria-haspopup="dialog" aria-expanded={open}
            className={`button sm quaternary br-1 realtime-processing-trigger${failed ? ' has-error' : ''}`}
            title="Processing status" onClick={() => setOpen(value => !value)}>
            <span>{label}</span><span aria-hidden>▾</span>
        </button>
        {open && createPortal(<div ref={panel} role="dialog" aria-label="Processing status" tabIndex={-1}
            className="realtime-processing-popover" style={{...position, maxHeight: `calc(100vh - ${position.top + 12}px)`}}>
            <div className="realtime-processing-heading"><strong>Processing status</strong>
                <button type="button" aria-label="Close processing details" onClick={close}>×</button></div>
            {!startup.snapshot && !startup.pending && !startup.statusUnavailable && !startup.statusError &&
                <p>Connect processing with the lightning button. Camera preview can run independently.</p>}
            <RealtimeStartupStatusView snapshot={startup.snapshot} statusError={startup.statusError}
        pending={startup.pending} statusUnavailable={startup.statusUnavailable} onStop={startup.stop} onRetry={startup.retry}/>
        </div>, document.body)}
    </>;
}
