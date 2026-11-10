import React, {useEffect, useRef, useState} from 'react';
import {StreamingOutputsPanel} from './StreamingOutputsPanel';
// The panel's settings disclosures use the settings grammar's chevron.
import '@/components/common/settings-layout/settings-layout.css';
import './streaming-outputs.css';

export function StreamingOutputsControl() {
    const [open, setOpen] = useState(false);
    const anchor = useRef<HTMLDivElement>(null);
    const trigger = useRef<HTMLButtonElement | null>(null);
    const close = () => {setOpen(false); trigger.current?.focus();};
    useEffect(() => {
        if (!open) return;
        const escape = (event: KeyboardEvent) => {
            if (event.key === 'Escape') {setOpen(false); trigger.current?.focus();}
        };
        const outside = (event: MouseEvent) => {
            if (!anchor.current?.contains(event.target as Node)) setOpen(false);
        };
        window.addEventListener('keydown', escape);
        document.addEventListener('mousedown', outside);
        return () => {
            window.removeEventListener('keydown', escape);
            document.removeEventListener('mousedown', outside);
        };
    }, [open]);
    return <div ref={anchor} className="modal-container pos-rel">
        <button ref={trigger} type="button" aria-label="Streaming outputs" aria-haspopup="dialog"
            aria-expanded={open} onClick={() => setOpen(value => !value)}
            className={`button sm quaternary br-1 flex items-center gap-1 ${open ? 'activated' : ''}`}>
            <span className="text bg text-gray">Outputs</span>
            <span aria-hidden className="text sm text-gray">▾</span>
        </button>
        {open && <div role="dialog" aria-label="Streaming outputs" className="streaming-outputs-flyout RTP-settings-flyout pos-abs right-0 border-1 border-black elevated-sharp flex flex-col p-1 bg-dark br-2 gap-1">
            <div className="flex flex-col p-2 gap-1 bg-middark br-1">
                <StreamingOutputsPanel onClose={close}/>
            </div>
        </div>}
    </div>;
}
