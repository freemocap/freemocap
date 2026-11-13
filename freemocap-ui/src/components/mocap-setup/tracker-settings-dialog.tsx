import {useEffect, useRef, type ReactNode} from 'react';
import {createPortal} from 'react-dom';
import ModalWindowControls from '@/components/ui-components/ModalWindowControls';
import ButtonSm from '@/components/ui-components/ButtonSm';
import '@/styles/mocap-settings.css';
import './dlc-model-settings.css';
import './tracker-settings-dialog.css';

export default function TrackerSettingsDialog({title, onClose, children}: {title: string; onClose: () => void; children: ReactNode}) {
    const dialog = useRef<HTMLDivElement>(null);
    useEffect(() => {
        const previous = document.activeElement as HTMLElement | null;
        dialog.current?.focus();
        return () => previous?.focus();
    }, []);
    return createPortal(<div className="tracker-dialog-overlay" onMouseDown={event => {
            event.stopPropagation();
            if (event.target === event.currentTarget) {
                event.preventDefault();
                onClose();
            }
        }}
        onKeyDown={event => {
            if (event.key === 'Escape') {event.stopPropagation(); onClose();}
            if (event.key === 'Tab') {
                const nodes = Array.from(dialog.current?.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), select:not(:disabled), summary, [role=button][tabindex="0"]') ?? [])
                    .filter(element => element.getClientRects().length > 0);
                if (!nodes?.length) return;
                const first = nodes[0], last = nodes[nodes.length - 1];
                if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog.current)) {event.preventDefault(); last.focus();}
                else if (!event.shiftKey && document.activeElement === last) {event.preventDefault(); first.focus();}
            }
        }}>
        <div ref={dialog} tabIndex={-1} role="dialog" aria-modal="true" aria-label={title} className="tracker-settings-modal">
            <ModalWindowControls title={title} onClose={onClose}/>
            <div className="modal-window-body tracker-settings-body settings-layout">{children}</div>
            <footer className="tracker-settings-footer"><ButtonSm text="Done" className="primary accent" textColor="text-white" onClick={onClose}/></footer>
        </div>
    </div>, document.body);
}
