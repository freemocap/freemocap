import React, { useEffect, useRef, memo } from 'react';
import { useServer } from '@/services/server/ServerContextProvider';
import {CharucoOverlayRenderer} from "@/services/server/server-helpers/overlay_renderer";

interface CameraViewProps {
    cameraId: string;
    scale?: number;
    maxWidth?: boolean;
}

/**
 * CameraView component - renders a canvas for a single camera feed with overlay.
 * Uses two stacked canvases:
 * - Bottom layer: Image canvas (managed by OffscreenCanvas worker)
 * - Top layer: Overlay canvas (for Charuco/ArUco detection visualization)
 */
export const CameraView: React.FC<CameraViewProps> = memo(({ cameraId, scale, maxWidth }) => {
    const imageCanvasRef = useRef<HTMLCanvasElement>(null);
    const overlayCanvasRef = useRef<HTMLCanvasElement>(null);
    const fpsDisplayRef = useRef<HTMLSpanElement>(null);
    const overlayRendererRef = useRef<CharucoOverlayRenderer | null>(null);

    const { setCanvasForCamera, getFps, registerOverlayRenderer } = useServer();
    const animationFrameRef = useRef<number | null>(null);

    // Set up image canvas (existing functionality)
    useEffect(() => {
        const canvas = imageCanvasRef.current;
        if (canvas && cameraId) {
            console.log(`Setting up image canvas for camera: ${cameraId}`);
            setCanvasForCamera(cameraId, canvas);
        }
    }, [cameraId, setCanvasForCamera]);

    // Set up overlay canvas and renderer
    useEffect(() => {
        const overlayCanvas = overlayCanvasRef.current;
        if (!overlayCanvas || !cameraId) return;

        console.log(`Setting up overlay renderer for camera: ${cameraId}`);

        try {
            const renderer = new CharucoOverlayRenderer(overlayCanvas);
            overlayRendererRef.current = renderer;

            // Register renderer with server context so it can receive updates
            registerOverlayRenderer(cameraId, renderer);

            return () => {
                console.log(`Cleaning up overlay renderer for camera: ${cameraId}`);
                renderer.destroy();
                overlayRendererRef.current = null;
            };
        } catch (error) {
            console.error(`Failed to create overlay renderer for camera ${cameraId}:`, error);
            throw error;
        }
    }, [cameraId, registerOverlayRenderer]);

    // Update FPS display using direct DOM manipulation to avoid React re-renders
    useEffect(() => {
        const updateFps = (): void => {
            const fps = getFps(cameraId);
            if (fpsDisplayRef.current && fps !== null) {
                fpsDisplayRef.current.textContent = `${fps.toFixed(1)} FPS`;
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
            position: 'absolute',
            top: 0,
            left: 0,
        };

        if (maxWidth) {
            return {
                ...baseStyle,
                width: '100%',
                height: '100%',
                objectFit: 'contain',
            };
        }

        if (scale !== undefined && scale !== 1.0) {
            return {
                ...baseStyle,
                width: `${scale * 100}%`,
                height: `${scale * 100}%`,
                objectFit: 'contain',
            };
        }

        // Default
        return {
            ...baseStyle,
            width: '100%',
            height: '100%',
            objectFit: 'contain',
        };
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
            {/* Image canvas (bottom layer) */}
            <canvas
                ref={imageCanvasRef}
                style={canvasStyle}
            />

            {/* Overlay canvas (top layer) */}
            <canvas
                ref={overlayCanvasRef}
                style={{
                    ...canvasStyle,
                    pointerEvents: 'none', // Allow clicks to pass through
                }}
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
