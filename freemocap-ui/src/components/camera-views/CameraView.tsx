import React, {memo, useEffect, useRef} from 'react';

import {useServer} from "@/hooks/useServer";

interface CameraViewProps {
    cameraId: string;
    scale?: number;
    maxWidth?: boolean;
}

/**
 * CameraView component - renders a canvas for a single camera feed.
 * The overlay is now composited directly into the frame before rendering.
 */
export const CameraView: React.FC<CameraViewProps> = memo(({ cameraId, scale, maxWidth }) => {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const fpsDisplayRef = useRef<HTMLSpanElement>(null);

    const { setCanvasForCamera, getFps } = useServer();
    const animationFrameRef = useRef<number | null>(null);

    // Set up canvas
    useEffect(() => {
        const canvas = canvasRef.current;
        if (canvas && cameraId) {
            console.log(`Setting up canvas for camera: ${cameraId}`);
            setCanvasForCamera(cameraId, canvas);
        }
    }, [cameraId, setCanvasForCamera]);

    // Update FPS display using direct DOM manipulation to avoid React re-renders
    useEffect(() => {
        const updateFps = (): void => {
            const fps = getFps(cameraId);
            if (fpsDisplayRef.current && fps !== null) {
                fpsDisplayRef.current.textContent = `Display FPS ${fps.toFixed(1)}`;
            }
            animationFrameRef.current = requestAnimationFrame(updateFps);
        };

        animationFrameRef.current = requestAnimationFrame(updateFps);

        return () => {
            if (animationFrameRef.current !== null) {
                cancelAnimationFrame(animationFrameRef.current);
            }
        };
    }, [cameraId, getFps]);

    // Calculate canvas styles based on scale and maxWidth settings
    const getCanvasStyle = (): React.CSSProperties => {
        const baseStyle: React.CSSProperties = {
            width: '100%',
            height: '100%',
            objectFit: 'contain',
        };

        if (maxWidth) {
            return baseStyle;
        }

        if (scale !== undefined && scale !== 1.0) {
            return {
                ...baseStyle,
                width: `${scale * 100}%`,
                height: `${scale * 100}%`,
            };
        }

        return baseStyle;
    };

    const canvasStyle = getCanvasStyle();

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
                overflow: 'hidden',
            }}
        >
            {/* Single canvas with composited image + overlay */}
            <canvas
                ref={canvasRef}
                style={canvasStyle}
            />

            {/* Info display */}
            <div
                style={{
                    position: 'absolute',
                    bottom: 8,
                    left: 8,
                    backgroundColor: 'rgba(0, 0, 0, 0.7)',
                    color: '#fff',
                    padding: '4px 8px',
                    borderRadius: 4,
                    fontSize: '12px',
                    fontFamily: 'monospace',
                    pointerEvents: 'none',
                }}
            >
                <div>{cameraId}</div>
                <div style={{ fontSize: '10px', marginTop: '2px', color: '#0f0' }}>
                    <span ref={fpsDisplayRef}>-- FPS</span>
                </div>
            </div>
        </div>
    );
}, (prevProps, nextProps) => {
    // Custom comparison: only re-render if relevant props change
    return (
        prevProps.cameraId === nextProps.cameraId &&
        prevProps.scale === nextProps.scale &&
        prevProps.maxWidth === nextProps.maxWidth
    );
});

CameraView.displayName = 'CameraView';
