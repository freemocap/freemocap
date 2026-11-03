import {useLayoutEffect, useRef, useState} from 'react';
import {PanelResizeHandles} from './PanelResizeHandles';
import IconButton from './IconButton';
import './modal-window.css';

/** Opt-in movement, resizing and maximizing for working dialogs. */
export default function ModalWindowControls({title, onClose}: {title: string; onClose?: () => void}) {
    const header = useRef<HTMLDivElement>(null);
    const panel = useRef<HTMLDivElement | null>(null);
    const restore = useRef<DOMRect | null>(null);
    const gesture = useRef<{x: number; y: number; bounds: DOMRect} | null>(null);
    const [maximized, setMaximized] = useState(false);
    function fitToViewport(bounds: {left: number; top: number; width: number; height: number}): void {
        if (!panel.current) return;
        const width = Math.min(bounds.width, innerWidth - 16);
        const height = Math.min(bounds.height, innerHeight - 16);
        Object.assign(panel.current.style, {
            left: `${Math.max(8, Math.min(bounds.left, innerWidth - width - 8))}px`,
            top: `${Math.max(8, Math.min(bounds.top, innerHeight - height - 8))}px`,
            width: `${width}px`, height: `${height}px`,
        });
    }
    useLayoutEffect(() => {
        const parent = header.current?.parentElement;
        if (!(parent instanceof HTMLDivElement)) throw new Error('Modal controls require a modal div parent.');
        panel.current = parent;
        const originalStyle = parent.style.cssText;
        const bounds = parent.getBoundingClientRect();
        parent.classList.add('modal-window');
        parent.setAttribute('role', 'dialog');
        if (!parent.hasAttribute('aria-label')) parent.setAttribute('aria-label', title);
        Object.assign(parent.style, {position: 'fixed', transform: 'none'});
        fitToViewport(bounds);
        return () => {parent.style.cssText = originalStyle; parent.classList.remove('modal-window'); panel.current = null;};
    }, [title]);
    useLayoutEffect(() => {
        const resize = () => {
            if (!panel.current) return;
            fitToViewport(maximized ? {left: 8, top: 8, width: innerWidth - 16, height: innerHeight - 16} : panel.current.getBoundingClientRect());
        };
        window.addEventListener('resize', resize);
        return () => window.removeEventListener('resize', resize);
    }, [maximized]);
    function maximize(): void {
        if (!panel.current) return;
        if (!maximized) {
            restore.current = panel.current.getBoundingClientRect();
            Object.assign(panel.current.style, {left: '8px', top: '8px', width: 'calc(100vw - 16px)', height: 'calc(100vh - 16px)'});
        } else if (restore.current) {
            const bounds = restore.current;
            fitToViewport(bounds);
        }
        setMaximized(!maximized);
    }
    return <>
        <div ref={header} className="modal-window-titlebar flex items-center justify-content-space-between"
            onDoubleClick={event => {if (!(event.target as HTMLElement).closest('button')) maximize();}}
            onPointerDown={event => {
                if (event.button !== 0 || maximized || (event.target as HTMLElement).closest('button') || !panel.current) return;
                event.preventDefault(); event.stopPropagation();
                gesture.current = {x: event.clientX, y: event.clientY, bounds: panel.current.getBoundingClientRect()};
                event.currentTarget.setPointerCapture(event.pointerId);
            }}
            onPointerMove={event => {
                if (!gesture.current || !panel.current) return;
                const {x, y, bounds} = gesture.current;
                panel.current.style.left = `${Math.max(8, Math.min(innerWidth - bounds.width - 8, bounds.left + event.clientX - x))}px`;
                panel.current.style.top = `${Math.max(8, Math.min(innerHeight - 40, bounds.top + event.clientY - y))}px`;
            }}
            onPointerUp={event => {gesture.current = null; if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);}}
            onPointerCancel={() => {gesture.current = null;}}>
            <span className="text md text-white">{title}</span>
            <div className="modal-window-actions">
                {onClose ? <>
                    <button type="button" className="modal-window-action" onClick={maximize}>{maximized ? 'Restore' : 'Maximize'}</button>
                    <button type="button" className="modal-window-action" aria-label={`Close ${title}`} onClick={onClose}>Close <span aria-hidden="true">×</span></button>
                </> : <IconButton icon="expand-icon" title={maximized ? 'Restore window size' : 'Maximize window'} onClick={maximize}/>}
            </div>
        </div>
        {!maximized && <PanelResizeHandles panelRef={panel}/>}
    </>;
}

