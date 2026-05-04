import React, {memo, useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {useServer} from '@/services/server/ServerContextProvider';
import {backendColor, frontendColor} from '@/components/framerate-viewer/FrameRateViewer';

interface CameraViewProps {
    cameraIndex: number;
    cameraId: string;
    scale?: number;
    maxWidth?: boolean;
}

/** How often (ms) to update the FPS display text. 4Hz is plenty for a number readout. */
const FPS_UPDATE_INTERVAL_MS = 250;

const MIN_ZOOM = .5;
const MAX_ZOOM = 100;
const ZOOM_SPEED = 0.0015;

/**
 * CameraView component - renders a canvas for a single camera feed.
 * Wrapped in memo to prevent re-renders when props haven't changed.
 * FPS display uses direct DOM manipulation via a low-frequency setInterval
 * instead of a per-component requestAnimationFrame loop.
 *
 * Supports scroll-to-zoom (mouse wheel + trackpad pinch) centered at the
 * cursor position, drag-to-pan when zoomed in, and touch pinch-to-zoom.
 */
export const CameraView: React.FC<CameraViewProps> = memo(({cameraIndex, cameraId, scale, maxWidth }) => {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const displayFpsRef = useRef<HTMLSpanElement>(null);
    const serverFpsRef = useRef<HTMLSpanElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const { setCanvasForCamera, getFps, getServerFps } = useServer();

    const [zoom, setZoom] = useState(1);
    const [pan, setPan] = useState<{x: number; y: number}>({x: 0, y: 0});
    const [isDragging, setIsDragging] = useState(false);

    // Refs mirror state so callbacks can always read the latest values without
    // depending on React state closures (avoids one-frame pan/zoom mismatch).
    const zoomRef = useRef(zoom);
    const panRef = useRef(pan);
    const isDraggingRef = useRef(isDragging);
    zoomRef.current = zoom;
    panRef.current = pan;
    isDraggingRef.current = isDragging;

    const dragStartRef = useRef<{x: number; y: number}>({x: 0, y: 0});
    const lastPinchDistanceRef = useRef<number | null>(null);
    const touchStartRef = useRef<{x: number; y: number} | null>(null);

    useEffect(() => {
        const canvas = canvasRef.current;

        if (canvas && cameraId) {
            setCanvasForCamera(cameraId, canvas);
        }
    }, [cameraId, setCanvasForCamera]);

    // Update FPS displays at a low frequency via setInterval
    useEffect(() => {
        const updateFps = () => {
            const displayFps = getFps(cameraId);
            if (displayFpsRef.current) {
                displayFpsRef.current.textContent = displayFps !== null
                    ? `${displayFps.toFixed(1)}`
                    : '--';
            }
            const srvFps = getServerFps();
            if (serverFpsRef.current) {
                serverFpsRef.current.textContent = srvFps !== null
                    ? `${srvFps.toFixed(1)}`
                    : '--';
            }
        };

        const intervalId = setInterval(updateFps, FPS_UPDATE_INTERVAL_MS);
        return () => clearInterval(intervalId);
    }, [cameraId, getFps, getServerFps]);

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
        dragStartRef.current = {x: e.clientX - currentPan.x, y: e.clientY - currentPan.y};
        setIsDragging(true);
    }, []);

    const handlePointerMove = useCallback((e: React.PointerEvent) => {
        if (!isDraggingRef.current) return;
        e.preventDefault();
        setPan({x: e.clientX - dragStartRef.current.x, y: e.clientY - dragStartRef.current.y});
    }, []);

    const handlePointerUp = useCallback((e: React.PointerEvent) => {
        if (!isDraggingRef.current) return;
        (e.target as HTMLElement).releasePointerCapture(e.pointerId);
        setIsDragging(false);
    }, []);

    // ── Touch: pinch-to-zoom (two fingers) + drag-to-pan (one finger) ──
    const getTouchDistance = (touches: React.TouchList): number => {
        const dx = touches[0].clientX - touches[1].clientX;
        const dy = touches[0].clientY - touches[1].clientY;
        return Math.sqrt(dx * dx + dy * dy);
    };

    const handleTouchStart = useCallback((e: React.TouchEvent) => {
        if (e.touches.length === 2) {
            e.preventDefault();
            lastPinchDistanceRef.current = getTouchDistance(e.touches);
            touchStartRef.current = null;
        } else if (e.touches.length === 1 && zoomRef.current > 1) {
            const touch = e.touches[0];
            const currentPan = panRef.current;
            dragStartRef.current = {x: touch.clientX - currentPan.x, y: touch.clientY - currentPan.y};
            touchStartRef.current = {x: touch.clientX, y: touch.clientY};
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
            setPan({x: touch.clientX - dragStartRef.current.x, y: touch.clientY - dragStartRef.current.y});
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
        setPan({x: 0, y: 0});
    }, []);

    const canvasStyle = useMemo((): React.CSSProperties => {
        if (maxWidth) {
            return { width: '100%', height: '100%', objectFit: 'contain' };
        }
        if (scale !== undefined && scale !== 1.0) {
            return { width: `${scale * 100}%`, height: `${scale * 100}%`, objectFit: 'contain' };
        }
        return { width: '100%', height: '100%', objectFit: 'contain' };
    }, [scale, maxWidth]);

    const isZoomed = zoom > 1;
    const cursor = isDragging ? 'grabbing' : isZoomed ? 'grab' : 'auto';

    const zoomWrapperStyle = useMemo((): React.CSSProperties => ({
        transform: `scale(${zoom}) translate(${pan.x / zoom}px, ${pan.y / zoom}px)`,
        transformOrigin: '0 0',
        width: '100%',
        height: '100%',
    }), [zoom, pan]);

    return (
        <div
            ref={containerRef}
            style={{
                width: '100%',
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                backgroundColor: '#000',
                position: 'relative',
                overflow: 'hidden',
                cursor,
            }}
            onPointerDown={handlePointerDown}
            onPointerMove={handlePointerMove}
            onPointerUp={handlePointerUp}
            onPointerLeave={handlePointerUp}
            onTouchStart={handleTouchStart}
            onTouchMove={handleTouchMove}
            onTouchEnd={handleTouchEnd}
            onDoubleClick={handleDoubleClick}
        >
            <div style={zoomWrapperStyle}>
                <canvas
                    ref={canvasRef}
                    style={canvasStyle}
                />
            </div>
            <div
                style={{
                    position: 'absolute',
                    bottom: 8,
                    left: 8,
                    backgroundColor: 'rgba(0, 0, 0, 0.75)',
                    color: '#fff',
                    padding: '4px 8px',
                    borderRadius: 4,
                    fontSize: '12px',
                    fontFamily: 'monospace',
                    lineHeight: 1.4,
                }}
            >
                <div style={{ fontSize: '10px', marginTop: '2px', display: 'flex', gap: '6px' }}>
                    <span style={{color:'#aaa'}}>#{cameraIndex} - {cameraId}</span>
                    <span style={{ color: frontendColor }}>
                        D:<span ref={displayFpsRef}>--</span>
                    </span>
                    <span style={{ color: backendColor }}>
                        S:<span ref={serverFpsRef}>--</span>
                    </span>
                    <span style={{ color: '#aaa' }}>fps</span>
                </div>
            </div>
        </div>
    );
}, (prevProps, nextProps) => {
    return prevProps.cameraId === nextProps.cameraId &&
        prevProps.scale === nextProps.scale &&
        prevProps.maxWidth === nextProps.maxWidth;
});

CameraView.displayName = 'CameraView';
