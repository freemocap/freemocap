import React, {memo, useEffect, useMemo, useRef} from 'react';
import {useServer} from '@/services/server/ServerContextProvider';
import {backendColor, frontendColor} from '@/components/framerate-viewer/FrameRateViewer';

interface CameraViewProps {
    cameraId: string;
    scale?: number;
    maxWidth?: boolean;
}

/** How often (ms) to update the FPS display text. 4Hz is plenty for a number readout. */
const FPS_UPDATE_INTERVAL_MS = 250;

/**
 * CameraView component - renders a canvas for a single camera feed.
 * Wrapped in memo to prevent re-renders when props haven't changed.
 * FPS display uses direct DOM manipulation via a low-frequency setInterval
 * instead of a per-component requestAnimationFrame loop.
 */
export const CameraView: React.FC<CameraViewProps> = memo(({ cameraId, scale, maxWidth }) => {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const displayFpsRef = useRef<HTMLSpanElement>(null);
    const serverFpsRef = useRef<HTMLSpanElement>(null);
    const { setCanvasForCamera, getFps, getServerFps } = useServer();

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

    const canvasStyle = useMemo((): React.CSSProperties => {
        if (maxWidth) {
            return { width: '100%', height: '100%', objectFit: 'contain' };
        }
        if (scale !== undefined && scale !== 1.0) {
            return { width: `${scale * 100}%`, height: `${scale * 100}%`, objectFit: 'contain' };
        }
        return { width: '100%', height: '100%', objectFit: 'contain' };
    }, [scale, maxWidth]);

    return (
        <div
            style={{
                width: '100%',
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                backgroundColor: '#000',
                position: 'relative',
                overflow: 'hidden'
            }}
        >
            <canvas
                ref={canvasRef}
                style={canvasStyle}
            />
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
                <div>{cameraId}</div>
                <div style={{ fontSize: '10px', marginTop: '2px', display: 'flex', gap: '6px' }}>
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
