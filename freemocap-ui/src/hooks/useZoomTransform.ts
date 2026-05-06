import {useCallback, useEffect, useMemo, useRef, useState} from 'react';

const MIN_ZOOM = 1.0;
const MAX_ZOOM = 100;
const ZOOM_SPEED = 0.0015;

function getTouchDistance(touches: React.TouchList): number {
    const dx = touches[0].clientX - touches[1].clientX;
    const dy = touches[0].clientY - touches[1].clientY;
    return Math.sqrt(dx * dx + dy * dy);
}

export interface ZoomTransformResult {
    /** CSS to apply to the content wrapper div (transform + transformOrigin + size) */
    zoomWrapperStyle: React.CSSProperties;
    /** Cursor to apply to the outer container */
    cursor: 'auto' | 'grab' | 'grabbing';
    /** Event handlers to spread onto the outer container div */
    containerHandlers: {
        onPointerDown: (e: React.PointerEvent<HTMLDivElement>) => void;
        onPointerMove: (e: React.PointerEvent<HTMLDivElement>) => void;
        onPointerUp: (e: React.PointerEvent<HTMLDivElement>) => void;
        onPointerLeave: (e: React.PointerEvent<HTMLDivElement>) => void;
        onTouchStart: (e: React.TouchEvent<HTMLDivElement>) => void;
        onTouchMove: (e: React.TouchEvent<HTMLDivElement>) => void;
        onTouchEnd: (e: React.TouchEvent<HTMLDivElement>) => void;
        onDoubleClick: () => void;
    };
}

/**
 * Encapsulates scroll-to-zoom (mouse wheel + trackpad pinch), drag-to-pan
 * when zoomed in, touch pinch-to-zoom, and double-click to reset.
 *
 * The caller must render an outer container div (overflow: hidden) with
 * a content-wrapper div (receiving `zoomWrapperStyle`). Event handlers
 * are spread onto the outer container. The native wheel listener is
 * attached to `containerRef.current` on mount.
 */
export function useZoomTransform(
    containerRef: React.RefObject<HTMLDivElement | null>,
): ZoomTransformResult {
    const [zoom, setZoom] = useState(1);
    const [pan, setPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
    const [isDragging, setIsDragging] = useState(false);

    // Refs mirror state so callbacks always read the latest values without
    // depending on React state closures (avoids one-frame pan/zoom mismatch).
    const zoomRef = useRef(zoom);
    const panRef = useRef(pan);
    const isDraggingRef = useRef(isDragging);
    zoomRef.current = zoom;
    panRef.current = pan;
    isDraggingRef.current = isDragging;

    const dragStartRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
    const lastPinchDistanceRef = useRef<number | null>(null);
    const touchStartRef = useRef<{ x: number; y: number } | null>(null);

    // ── Wheel: scroll-to-zoom centered at cursor ────────────────────────
    // Must be a native listener with {passive: false} so e.preventDefault()
    // is guaranteed to fire. React's onWheel is delegated to the root element
    // (React 17+) where Chrome silently ignores preventDefault on passive
    // listeners — the panel scrolls slightly, shifting getBoundingClientRect()
    // between events and drifting the zoom anchor away from the cursor.
    useEffect(() => {
        const container = containerRef.current;
        if (!container) return;

        const onWheel = (e: WheelEvent) => {
            e.preventDefault();

            const rect = container.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            const mouseY = e.clientY - rect.top;

            const currentZoom = zoomRef.current;
            const currentPan = panRef.current;

            const newZoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, currentZoom * (1 - e.deltaY * ZOOM_SPEED)));
            if (newZoom === currentZoom) return;

            const ratio = newZoom / currentZoom;
            setZoom(newZoom);
            setPan(newZoom <= MIN_ZOOM
                ? { x: 0, y: 0 }
                : {
                    x: mouseX - (mouseX - currentPan.x) * ratio,
                    y: mouseY - (mouseY - currentPan.y) * ratio,
                });
        };

        container.addEventListener('wheel', onWheel, { passive: false });
        return () => container.removeEventListener('wheel', onWheel);
    }, []);

    // ── Pointer: drag-to-pan when zoomed in (mouse only) ────────────────
    const handlePointerDown = useCallback((e: React.PointerEvent) => {
        if (e.pointerType === 'touch') return;
        if (zoomRef.current <= 1) return;
        e.preventDefault();
        e.stopPropagation();
        (e.target as HTMLElement).setPointerCapture(e.pointerId);
        const currentPan = panRef.current;
        dragStartRef.current = { x: e.clientX - currentPan.x, y: e.clientY - currentPan.y };
        setIsDragging(true);
    }, []);

    const handlePointerMove = useCallback((e: React.PointerEvent) => {
        if (!isDraggingRef.current) return;
        e.preventDefault();
        setPan({ x: e.clientX - dragStartRef.current.x, y: e.clientY - dragStartRef.current.y });
    }, []);

    const handlePointerUp = useCallback((e: React.PointerEvent) => {
        if (!isDraggingRef.current) return;
        (e.target as HTMLElement).releasePointerCapture(e.pointerId);
        setIsDragging(false);
    }, []);

    // ── Touch: pinch-to-zoom (two fingers) + drag-to-pan (one finger) ──
    const handleTouchStart = useCallback((e: React.TouchEvent) => {
        if (e.touches.length === 2) {
            e.preventDefault();
            lastPinchDistanceRef.current = getTouchDistance(e.touches);
            touchStartRef.current = null;
        } else if (e.touches.length === 1 && zoomRef.current > 1) {
            const touch = e.touches[0];
            const currentPan = panRef.current;
            dragStartRef.current = { x: touch.clientX - currentPan.x, y: touch.clientY - currentPan.y };
            touchStartRef.current = { x: touch.clientX, y: touch.clientY };
        }
    }, []);

    const handleTouchMove = useCallback((e: React.TouchEvent) => {
        const lastDist = lastPinchDistanceRef.current;

        if (e.touches.length === 2 && lastDist !== null) {
            e.preventDefault();
            e.stopPropagation();

            const dist = getTouchDistance(e.touches);
            const container = containerRef.current;
            if (!container) return;

            const rect = container.getBoundingClientRect();
            const midX = (e.touches[0].clientX + e.touches[1].clientX) / 2 - rect.left;
            const midY = (e.touches[0].clientY + e.touches[1].clientY) / 2 - rect.top;

            const currentZoom = zoomRef.current;
            const currentPan = panRef.current;

            const newZoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, currentZoom * (dist / lastDist)));
            if (newZoom === currentZoom) return;

            const ratio = newZoom / currentZoom;
            setPan({
                x: midX - (midX - currentPan.x) * ratio,
                y: midY - (midY - currentPan.y) * ratio,
            });
            setZoom(newZoom);
            lastPinchDistanceRef.current = dist;
        } else if (e.touches.length === 1 && zoomRef.current > 1 && touchStartRef.current !== null) {
            e.preventDefault();
            const touch = e.touches[0];
            setPan({ x: touch.clientX - dragStartRef.current.x, y: touch.clientY - dragStartRef.current.y });
        }
    }, []);

    const handleTouchEnd = useCallback((e: React.TouchEvent) => {
        if (e.touches.length < 2) {
            lastPinchDistanceRef.current = null;
        }
        if (e.touches.length === 0) {
            touchStartRef.current = null;
        }
    }, []);

    // ── Double-click: reset zoom ────────────────────────────────────────
    const handleDoubleClick = useCallback(() => {
        setZoom(1);
        setPan({ x: 0, y: 0 });
    }, []);

    // ── Computed values ─────────────────────────────────────────────────
    const isZoomed = zoom > 1;
    const cursor: 'auto' | 'grab' | 'grabbing' =
        isDragging ? 'grabbing' : isZoomed ? 'grab' : 'auto';

    const zoomWrapperStyle = useMemo((): React.CSSProperties => {
        const style: React.CSSProperties = {
            width: '100%',
            height: '100%',
        };
        // Only apply transform when there's actual zoom or pan.
        // CSS transform (even scale(1)) creates a new containing block
        // that can break percentage-height resolution in flex layouts.
        if (zoom !== 1 || pan.x !== 0 || pan.y !== 0) {
            style.transform = `scale(${zoom}) translate(${pan.x / zoom}px, ${pan.y / zoom}px)`;
            style.transformOrigin = '0 0';
        }
        return style;
    }, [zoom, pan]);

    const containerHandlers = useMemo(() => ({
        onPointerDown: handlePointerDown,
        onPointerMove: handlePointerMove,
        onPointerUp: handlePointerUp,
        onPointerLeave: handlePointerUp,
        onTouchStart: handleTouchStart,
        onTouchMove: handleTouchMove,
        onTouchEnd: handleTouchEnd,
        onDoubleClick: handleDoubleClick,
    }), [handlePointerDown, handlePointerMove, handlePointerUp, handleTouchStart, handleTouchMove, handleTouchEnd, handleDoubleClick]);

    return { zoomWrapperStyle, cursor, containerHandlers };
}
