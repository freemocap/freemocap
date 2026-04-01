import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Box } from '@mui/material';
import { CameraView } from './CameraView';

interface ResizableCameraViewProps {
    cameraId: string;
    /** Initial position/size from the auto-layout */
    initialX: number;
    initialY: number;
    initialWidth: number;
    initialHeight: number;
    /** Called when the user finishes moving or resizing this view */
    onLayoutChange: (cameraId: string, x: number, y: number, w: number, h: number) => void;
    /** Bring this camera to front when interacted with */
    onFocus: (cameraId: string) => void;
    zIndex: number;
}

const MIN_WIDTH = 120;
const MIN_HEIGHT = 90;

const HANDLE_SIZE = 16;

type DragMode = 'none' | 'move' | 'resize';

/**
 * A single camera view window that can be freely dragged (by its body)
 * and resized (by a bottom-right handle) within an absolute-positioned container.
 */
export const ResizableCameraView: React.FC<ResizableCameraViewProps> = ({
    cameraId,
    initialX,
    initialY,
    initialWidth,
    initialHeight,
    onLayoutChange,
    onFocus,
    zIndex,
}) => {
    const [x, setX] = useState<number>(initialX);
    const [y, setY] = useState<number>(initialY);
    const [width, setWidth] = useState<number>(initialWidth);
    const [height, setHeight] = useState<number>(initialHeight);
    const [dragMode, setDragMode] = useState<DragMode>('none');

    // Sync when parent resets layout
    useEffect(() => {
        setX(initialX);
        setY(initialY);
        setWidth(initialWidth);
        setHeight(initialHeight);
    }, [initialX, initialY, initialWidth, initialHeight]);

    const dragRef = useRef<{
        startMouseX: number;
        startMouseY: number;
        startX: number;
        startY: number;
        startW: number;
        startH: number;
    } | null>(null);

    const handlePointerDown = useCallback((e: React.PointerEvent<HTMLDivElement>, mode: DragMode) => {
        e.preventDefault();
        e.stopPropagation();
        onFocus(cameraId);

        dragRef.current = {
            startMouseX: e.clientX,
            startMouseY: e.clientY,
            startX: x,
            startY: y,
            startW: width,
            startH: height,
        };
        setDragMode(mode);
        (e.target as HTMLElement).setPointerCapture(e.pointerId);
    }, [cameraId, x, y, width, height, onFocus]);

    const handlePointerMove = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
        if (dragMode === 'none' || !dragRef.current) return;

        const { startMouseX, startMouseY, startX, startY, startW, startH } = dragRef.current;
        const dx = e.clientX - startMouseX;
        const dy = e.clientY - startMouseY;

        if (dragMode === 'move') {
            setX(startX + dx);
            setY(startY + dy);
        } else if (dragMode === 'resize') {
            setWidth(Math.max(MIN_WIDTH, startW + dx));
            setHeight(Math.max(MIN_HEIGHT, startH + dy));
        }
    }, [dragMode]);

    const handlePointerUp = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
        if (dragMode === 'none' || !dragRef.current) return;

        const { startMouseX, startMouseY, startX, startY, startW, startH } = dragRef.current;
        const dx = e.clientX - startMouseX;
        const dy = e.clientY - startMouseY;

        let finalX = startX;
        let finalY = startY;
        let finalW = startW;
        let finalH = startH;

        if (dragMode === 'move') {
            finalX = startX + dx;
            finalY = startY + dy;
        } else if (dragMode === 'resize') {
            finalW = Math.max(MIN_WIDTH, startW + dx);
            finalH = Math.max(MIN_HEIGHT, startH + dy);
        }

        setX(finalX);
        setY(finalY);
        setWidth(finalW);
        setHeight(finalH);
        onLayoutChange(cameraId, finalX, finalY, finalW, finalH);

        setDragMode('none');
        dragRef.current = null;
        (e.target as HTMLElement).releasePointerCapture(e.pointerId);
    }, [dragMode, cameraId, onLayoutChange]);

    // Suppress text selection during drag
    useEffect(() => {
        if (dragMode !== 'none') {
            document.body.style.userSelect = 'none';
            document.body.style.cursor = dragMode === 'move' ? 'grabbing' : 'nwse-resize';
            return () => {
                document.body.style.userSelect = '';
                document.body.style.cursor = '';
            };
        }
    }, [dragMode]);

    const isActive = dragMode !== 'none';

    return (
        <Box
            sx={{
                position: 'absolute',
                left: x,
                top: y,
                width,
                height,
                zIndex,
                border: '1px solid',
                borderColor: isActive ? 'primary.main' : 'rgba(255,255,255,0.15)',
                borderRadius: '4px',
                overflow: 'hidden',
                boxShadow: isActive ? 4 : 1,
                transition: isActive ? 'none' : 'border-color 0.15s ease, box-shadow 0.15s ease',
                '&:hover': {
                    borderColor: 'rgba(255,255,255,0.4)',
                },
            }}
        >
            {/* Draggable move area covers the entire camera view */}
            <Box
                onPointerDown={(e) => handlePointerDown(e, 'move')}
                onPointerMove={handlePointerMove}
                onPointerUp={handlePointerUp}
                sx={{
                    width: '100%',
                    height: '100%',
                    cursor: dragMode === 'move' ? 'grabbing' : 'grab',
                }}
            >
                <CameraView cameraId={cameraId} />
            </Box>

            {/* Resize handle in the bottom-right corner */}
            <Box
                onPointerDown={(e) => handlePointerDown(e, 'resize')}
                onPointerMove={handlePointerMove}
                onPointerUp={handlePointerUp}
                sx={{
                    position: 'absolute',
                    bottom: 0,
                    right: 0,
                    width: HANDLE_SIZE,
                    height: HANDLE_SIZE,
                    cursor: 'nwse-resize',
                    zIndex: 2,
                    '&::after': {
                        content: '""',
                        position: 'absolute',
                        bottom: 2,
                        right: 2,
                        width: 8,
                        height: 8,
                        borderRight: '2px solid',
                        borderBottom: '2px solid',
                        borderColor: isActive ? 'primary.main' : 'rgba(255,255,255,0.45)',
                    },
                    '&:hover::after': {
                        borderColor: 'primary.main',
                    },
                }}
            />
        </Box>
    );
};
