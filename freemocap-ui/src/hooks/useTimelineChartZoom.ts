import {useCallback, useEffect, useMemo, useRef, useState, type RefObject} from 'react';
import {
    panTimelineByPixels,
    resolveVisibleTimelineWindow,
    type TimelineZoomState,
    type VisibleTimelineWindow,
    zoomTimelineAtPointer,
} from '@/components/pipeline-metrics/pipelineTimelineModel';

type Options = {
    baseStartMs: number;
    baseDurationMs: number;
    labelWidthPx: number;
    chartPaddingRightPx?: number;
};

export function useTimelineChartZoom({
    baseStartMs,
    baseDurationMs,
    labelWidthPx,
    chartPaddingRightPx = 8,
}: Options): {
    containerRef: RefObject<HTMLDivElement | null>;
    visibleWindow: VisibleTimelineWindow;
    isZoomed: boolean;
    resetZoom: () => void;
    zoomIn: () => void;
    zoomOut: () => void;
    chartCursor: 'default' | 'grab' | 'grabbing';
    chartHandlers: {
        onPointerDown: (event: React.PointerEvent<HTMLDivElement>) => void;
        onPointerMove: (event: React.PointerEvent<HTMLDivElement>) => void;
        onPointerUp: (event: React.PointerEvent<HTMLDivElement>) => void;
        onPointerLeave: (event: React.PointerEvent<HTMLDivElement>) => void;
        onDoubleClick: () => void;
    };
} {
    const containerRef = useRef<HTMLDivElement | null>(null);
    const [zoomState, setZoomState] = useState<TimelineZoomState>({zoomLevel: 1, panMs: 0});
    const [isDragging, setIsDragging] = useState(false);
    const dragLastXRef = useRef(0);
    const zoomStateRef = useRef(zoomState);
    zoomStateRef.current = zoomState;

    useEffect(() => {
        setZoomState({zoomLevel: 1, panMs: 0});
    }, [baseStartMs, baseDurationMs]);

    const visibleWindow = useMemo(
        () => resolveVisibleTimelineWindow(
            baseStartMs,
            baseDurationMs,
            zoomState.zoomLevel,
            zoomState.panMs,
        ),
        [baseDurationMs, baseStartMs, zoomState.panMs, zoomState.zoomLevel],
    );

    const getChartMetrics = useCallback((clientX: number) => {
        const container = containerRef.current;
        if (!container) {
            return null;
        }
        const rect = container.getBoundingClientRect();
        const chartLeft = rect.left + labelWidthPx;
        const chartWidth = rect.width - labelWidthPx - chartPaddingRightPx;
        if (chartWidth <= 0) {
            return null;
        }
        const pointerRatio = (clientX - chartLeft) / chartWidth;
        return {chartWidth, pointerRatio};
    }, [chartPaddingRightPx, labelWidthPx]);

    const applyZoomAtClientX = useCallback((clientX: number, zoomIn: boolean) => {
        const metrics = getChartMetrics(clientX);
        if (!metrics) return;
        const current = zoomStateRef.current;
        setZoomState(zoomTimelineAtPointer(
            baseStartMs,
            baseDurationMs,
            current.zoomLevel,
            current.panMs,
            metrics.pointerRatio,
            zoomIn,
        ));
    }, [baseDurationMs, baseStartMs, getChartMetrics]);

    useEffect(() => {
        const container = containerRef.current;
        if (!container) return;

        const onWheel = (event: WheelEvent) => {
            const metrics = getChartMetrics(event.clientX);
            if (!metrics || event.clientX < container.getBoundingClientRect().left + labelWidthPx) {
                return;
            }
            event.preventDefault();
            const current = zoomStateRef.current;
            setZoomState(zoomTimelineAtPointer(
                baseStartMs,
                baseDurationMs,
                current.zoomLevel,
                current.panMs,
                metrics.pointerRatio,
                event.deltaY < 0,
            ));
        };

        container.addEventListener('wheel', onWheel, {passive: false});
        return () => container.removeEventListener('wheel', onWheel);
    }, [baseDurationMs, baseStartMs, getChartMetrics, labelWidthPx]);

    const resetZoom = useCallback(() => {
        setZoomState({zoomLevel: 1, panMs: 0});
    }, []);

    const zoomIn = useCallback(() => {
        const container = containerRef.current;
        if (!container) return;
        const rect = container.getBoundingClientRect();
        applyZoomAtClientX(rect.left + labelWidthPx + (rect.width - labelWidthPx) / 2, true);
    }, [applyZoomAtClientX, labelWidthPx]);

    const zoomOut = useCallback(() => {
        const container = containerRef.current;
        if (!container) return;
        const rect = container.getBoundingClientRect();
        applyZoomAtClientX(rect.left + labelWidthPx + (rect.width - labelWidthPx) / 2, false);
    }, [applyZoomAtClientX, labelWidthPx]);

    const onPointerDown = useCallback((event: React.PointerEvent<HTMLDivElement>) => {
        if (event.button !== 0 || visibleWindow.zoomLevel <= 1 || !event.shiftKey) return;
        if (event.clientX < event.currentTarget.getBoundingClientRect().left + labelWidthPx) return;
        event.currentTarget.setPointerCapture(event.pointerId);
        dragLastXRef.current = event.clientX;
        setIsDragging(true);
    }, [labelWidthPx, visibleWindow.zoomLevel]);

    const onPointerMove = useCallback((event: React.PointerEvent<HTMLDivElement>) => {
        if (!isDragging) return;
        const metrics = getChartMetrics(event.clientX);
        if (!metrics) return;
        const deltaPixels = event.clientX - dragLastXRef.current;
        dragLastXRef.current = event.clientX;
        const current = zoomStateRef.current;
        setZoomState(panTimelineByPixels(
            baseStartMs,
            baseDurationMs,
            current.zoomLevel,
            current.panMs,
            deltaPixels,
            metrics.chartWidth,
        ));
    }, [baseDurationMs, baseStartMs, getChartMetrics, isDragging]);

    const endDrag = useCallback((event: React.PointerEvent<HTMLDivElement>) => {
        if (!isDragging) return;
        if (event.currentTarget.hasPointerCapture(event.pointerId)) {
            event.currentTarget.releasePointerCapture(event.pointerId);
        }
        setIsDragging(false);
    }, [isDragging]);

    return {
        containerRef,
        visibleWindow,
        isZoomed: visibleWindow.zoomLevel > 1,
        resetZoom,
        zoomIn,
        zoomOut,
        chartCursor: isDragging ? 'grabbing' : visibleWindow.zoomLevel > 1 ? 'grab' : 'default',
        chartHandlers: {
            onPointerDown,
            onPointerMove,
            onPointerUp: endDrag,
            onPointerLeave: endDrag,
            onDoubleClick: resetZoom,
        },
    };
}
