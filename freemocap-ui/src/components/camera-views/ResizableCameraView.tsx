import React, {useCallback, useEffect, useRef, useState} from 'react';
import {CameraView} from './CameraView';

interface ResizableCameraViewProps {
    cameraIndex: number;
    cameraId: string;
    initialX: number;
    initialY: number;
    initialWidth: number;
    initialHeight: number;
    onLayoutChange: (cameraId: string, x: number, y: number, w: number, h: number) => void;
    onFocus: (cameraId: string) => void;
    zIndex: number;
}

const MIN_WIDTH = 120;
const MIN_HEIGHT = 90;
const HANDLE_SIZE = 16;

type DragMode = 'none' | 'move' | 'resize';

export const ResizableCameraView: React.FC<ResizableCameraViewProps> = ({
    cameraIndex,
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
        <div
            className="pos-abs overflow-hidden br-1"
            style={{
                left: x,
                top: y,
                width,
                height,
                zIndex,
                border: `1px solid ${isActive ? 'var(--color-info)' : 'rgba(255,255,255,0.15)'}`,
                boxShadow: isActive ? '0 4px 12px rgba(0,0,0,0.4)' : '0 1px 4px rgba(0,0,0,0.2)',
                transition: isActive ? 'none' : 'border-color 0.15s ease, box-shadow 0.15s ease',
            }}
        >
            <div
                onPointerDown={(e) => handlePointerDown(e, 'move')}
                onPointerMove={handlePointerMove}
                onPointerUp={handlePointerUp}
                className="w-full h-full"
                style={{
                    cursor: dragMode === 'move' ? 'grabbing' : 'grab',
                }}
            >
                <CameraView cameraIndex={cameraIndex} cameraId={cameraId} />
            </div>

            <div
                onPointerDown={(e) => handlePointerDown(e, 'resize')}
                onPointerMove={handlePointerMove}
                onPointerUp={handlePointerUp}
                className="pos-abs bottom-0 right-0 z-2"
                style={{
                    width: HANDLE_SIZE,
                    height: HANDLE_SIZE,
                    cursor: 'nwse-resize',
                }}
            />
        </div>
    );
};
