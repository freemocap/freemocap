import {useRef, type CSSProperties, type KeyboardEvent, type PointerEvent, type RefObject} from 'react';

enum ResizeEdge { Top, Right, Bottom, Left, TopLeft, TopRight, BottomLeft, BottomRight }

interface ResizeHandle {
    edge: ResizeEdge;
    label: string;
    style: CSSProperties;
    horizontal: number;
    vertical: number;
}

const handles: ResizeHandle[] = [
    {edge: ResizeEdge.Top, label: 'top', horizontal: 0, vertical: -1, style: {top: 0, left: 12, right: 12, height: 6, cursor: 'ns-resize'}},
    {edge: ResizeEdge.Right, label: 'right', horizontal: 1, vertical: 0, style: {right: 0, top: 12, bottom: 12, width: 6, cursor: 'ew-resize'}},
    {edge: ResizeEdge.Bottom, label: 'bottom', horizontal: 0, vertical: 1, style: {bottom: 0, left: 12, right: 12, height: 6, cursor: 'ns-resize'}},
    {edge: ResizeEdge.Left, label: 'left', horizontal: -1, vertical: 0, style: {left: 0, top: 12, bottom: 12, width: 6, cursor: 'ew-resize'}},
    {edge: ResizeEdge.TopLeft, label: 'top left', horizontal: -1, vertical: -1, style: {top: 0, left: 0, width: 12, height: 12, cursor: 'nwse-resize'}},
    {edge: ResizeEdge.TopRight, label: 'top right', horizontal: 1, vertical: -1, style: {top: 0, right: 0, width: 12, height: 12, cursor: 'nesw-resize'}},
    {edge: ResizeEdge.BottomLeft, label: 'bottom left', horizontal: -1, vertical: 1, style: {bottom: 0, left: 0, width: 12, height: 12, cursor: 'nesw-resize'}},
    {edge: ResizeEdge.BottomRight, label: 'bottom right', horizontal: 1, vertical: 1, style: {bottom: 0, right: 0, width: 12, height: 12, cursor: 'nwse-resize'}},
];

interface ResizeGesture { x: number; y: number; bounds: DOMRect; pointerId: number }

export function PanelResizeHandles({panelRef}: {panelRef: RefObject<HTMLDivElement | null>}): React.ReactElement {
    const gesture = useRef<ResizeGesture | null>(null);

    function resize(handle: ResizeHandle, bounds: DOMRect, dx: number, dy: number): void {
        const panel = panelRef.current;
        if (!panel) return;
        const margin = 16;
        const minWidth = Math.min(320, window.innerWidth - margin * 2);
        const minHeight = Math.min(200, window.innerHeight - margin * 2);
        const left = handle.horizontal < 0 ? Math.max(margin, Math.min(bounds.left + dx, bounds.right - minWidth)) : bounds.left;
        const right = handle.horizontal > 0 ? Math.min(window.innerWidth - margin, Math.max(bounds.right + dx, bounds.left + minWidth)) : bounds.right;
        const top = handle.vertical < 0 ? Math.max(margin, Math.min(bounds.top + dy, bounds.bottom - minHeight)) : bounds.top;
        const bottom = handle.vertical > 0 ? Math.min(window.innerHeight - margin, Math.max(bounds.bottom + dy, bounds.top + minHeight)) : bounds.bottom;
        Object.assign(panel.style, {left: `${left}px`, top: `${top}px`, width: `${right - left}px`, height: `${bottom - top}px`, transform: 'none'});
    }

    function start(event: PointerEvent<HTMLDivElement>): void {
        if (event.button !== 0 || !panelRef.current) return;
        event.preventDefault();
        event.stopPropagation();
        gesture.current = {x: event.clientX, y: event.clientY, bounds: panelRef.current.getBoundingClientRect(), pointerId: event.pointerId};
        event.currentTarget.setPointerCapture(event.pointerId);
    }

    function move(event: PointerEvent<HTMLDivElement>, handle: ResizeHandle): void {
        if (!gesture.current || gesture.current.pointerId !== event.pointerId) return;
        resize(handle, gesture.current.bounds, event.clientX - gesture.current.x, event.clientY - gesture.current.y);
    }

    function keyboard(event: KeyboardEvent<HTMLDivElement>, handle: ResizeHandle): void {
        const step = event.shiftKey ? 50 : 10;
        const dx = event.key === 'ArrowLeft' ? -step : event.key === 'ArrowRight' ? step : 0;
        const dy = event.key === 'ArrowUp' ? -step : event.key === 'ArrowDown' ? step : 0;
        if ((!dx && !dy) || !panelRef.current) return;
        event.preventDefault();
        resize(handle, panelRef.current.getBoundingClientRect(), dx, dy);
    }

    return <>{handles.map(handle => <div
        key={handle.edge}
        role="button"
        tabIndex={0}
        aria-label={`Resize panel from ${handle.label} edge`}
        title="Drag to resize; use arrow keys when focused"
        style={{position: 'absolute', zIndex: 2, touchAction: 'none', ...handle.style}}
        onPointerDown={start}
        onPointerMove={event => move(event, handle)}
        onPointerUp={event => {
            gesture.current = null;
            if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
        }}
        onPointerCancel={() => { gesture.current = null; }}
        onLostPointerCapture={() => { gesture.current = null; }}
        onKeyDown={event => keyboard(event, handle)}
    />)}</>;
}
