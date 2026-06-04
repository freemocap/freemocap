import React, { useState, useCallback, useRef, useEffect, useMemo } from "react";
import clsx from "clsx";
import ReactGridLayout, { noCompactor } from "react-grid-layout";
import type { Layout, LayoutItem } from "react-grid-layout";
import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";
import { CameraGridCell } from "./CameraGridCell";
import { useServer } from "@/services/server/ServerContextProvider";
import { useTranslation } from "react-i18next";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { selectConnectedCameras } from "@/store/slices/cameras/cameras-selectors";
import { camerasConnectOrUpdate } from "@/store/slices/cameras/cameras-thunks";
import CameraEmptyState from "@/components/ui-components/camerasEmptyState";
import { useRecordingGuard } from "@/components/RecordingGuardProvider";

const GRID_COLS = 12;
const MARGIN: [number, number] = [4, 4];

interface Tiling { cols: number; rows: number; }

function computeOptimalTiling(n: number, containerWidth: number, containerHeight: number): Tiling {
    if (n <= 1) return { cols: 1, rows: 1 };
    let bestCols = 1, bestArea = 0;
    for (let cols = 1; cols <= n; cols++) {
        const rows = Math.ceil(n / cols);
        const cellW = (containerWidth - MARGIN[0] * (cols - 1)) / cols;
        const cellH = (containerHeight - MARGIN[1] * (rows - 1)) / rows;
        if (cellW < 80 || cellH < 60) continue;
        const totalArea = n * cellW * cellH;
        if (totalArea > bestArea) { bestArea = totalArea; bestCols = cols; }
    }
    return { cols: bestCols, rows: Math.ceil(n / bestCols) };
}

function tilingFromColumns(n: number, cols: number): Tiling {
    if (n === 0) return { cols: 1, rows: 1 };
    const clamped = Math.max(1, Math.min(cols, n));
    return { cols: clamped, rows: Math.ceil(n / clamped) };
}

function buildLayout(cameraIds: string[], tiling: Tiling): LayoutItem[] {
    if (cameraIds.length === 0) return [];
    const colSpan = Math.floor(GRID_COLS / tiling.cols);
    return cameraIds.map((id, i) => ({
        i: id, x: (i % tiling.cols) * colSpan, y: Math.floor(i / tiling.cols),
        w: colSpan, h: 1, minW: 1, minH: 1,
    }));
}

interface CameraViewsGridProps {
    manualColumns: number | null;
    resetKey: number;
}

export const CameraViewsGrid: React.FC<CameraViewsGridProps> = ({ manualColumns, resetKey }) => {
    const { connectedCameraIds } = useServer();
    const dispatch = useAppDispatch();
    const { requestGuardedAction } = useRecordingGuard();
    const [isConnecting, setIsConnecting] = useState(false);

    const handleConnect = () => {
        requestGuardedAction('Stop Recording & Update Camera Config', async () => {
            setIsConnecting(true);
            try { await dispatch(camerasConnectOrUpdate()).unwrap(); }
            catch { /* error handled by store */ }
            finally { setIsConnecting(false); }
        });
    };
    const { t } = useTranslation();
    const isRecording = useAppSelector(state => state.recording.isRecording);
    const containerRef = useRef<HTMLDivElement>(null);
    const [containerWidth, setContainerWidth] = useState<number>(800);
    const [containerHeight, setContainerHeight] = useState<number>(600);

    useEffect(() => {
        const el = containerRef.current?.parentElement;
        if (!el) return;
        const measure = () => {
            const { width, height } = el.getBoundingClientRect();
            setContainerWidth(width);
            setContainerHeight(height);
        };
        measure();
        const observer = new ResizeObserver(measure);
        observer.observe(el);
        return () => observer.disconnect();
    }, []);

    const connectedCameras = useAppSelector(selectConnectedCameras);
    const configFingerprint = useMemo(() =>
        connectedCameras.map(cam =>
            `${cam.id}:${cam.actualConfig.rotation}:${cam.actualConfig.resolution.width}x${cam.actualConfig.resolution.height}`
        ).join("|"),
        [connectedCameras]
    );

    const sortedConnectedCameraIds = useMemo(() => {
        const activeSet = new Set(connectedCameraIds);
        return connectedCameras.filter(c => activeSet.has(c.id)).map(c => c.id);
    }, [connectedCameraIds, connectedCameras]);

    const prevTilingRef = useRef<Tiling>({ cols: 1, rows: 1 });
    const tiling = useMemo(() => {
        const candidate = manualColumns !== null
            ? tilingFromColumns(connectedCameraIds.length, manualColumns)
            : computeOptimalTiling(connectedCameraIds.length, containerWidth, containerHeight);
        const prev = prevTilingRef.current;
        if (candidate.cols === prev.cols && candidate.rows === prev.rows) return prev;
        prevTilingRef.current = candidate;
        return candidate;
    }, [connectedCameraIds.length, containerWidth, containerHeight, manualColumns]);

    const [layout, setLayout] = useState<LayoutItem[]>(() => buildLayout(sortedConnectedCameraIds, tiling));

    useEffect(() => {
        setLayout(buildLayout(sortedConnectedCameraIds, tiling));
    }, [sortedConnectedCameraIds, tiling, resetKey, configFingerprint]);

    const layoutBeforeDragRef = useRef<LayoutItem[]>(layout);
    const handleDragStart = useCallback(() => { layoutBeforeDragRef.current = layout; }, [layout]);

    const handleDragStop = useCallback((_: Layout, _old: LayoutItem | null, newItem: LayoutItem | null) => {
        if (!newItem) return;
        const preDrag = layoutBeforeDragRef.current;
        const draggedBefore = preDrag.find(l => l.i === newItem.i);
        if (!draggedBefore) return;
        const swapTarget = preDrag.find(l => l.i !== newItem.i
            && newItem.x < l.x + l.w && newItem.x + newItem.w > l.x
            && newItem.y < l.y + l.h && newItem.y + newItem.h > l.y);
        if (swapTarget) {
            setLayout(preDrag.map(l => {
                if (l.i === newItem.i) return { ...l, x: swapTarget.x, y: swapTarget.y };
                if (l.i === swapTarget.i) return { ...l, x: draggedBefore.x, y: draggedBefore.y };
                return l;
            }));
        } else {
            setLayout(preDrag.map(l => l.i === newItem.i
                ? { ...l, x: Math.max(0, Math.min(newItem.x, GRID_COLS - newItem.w)), y: Math.max(0, Math.min(newItem.y, tiling.rows - newItem.h)) }
                : l
            ));
        }
    }, [tiling.rows]);

    const handleLayoutChange = useCallback((_: Layout) => {}, []);
    const handleResizeStop = useCallback((newLayout: Layout) => { setLayout([...newLayout]); }, []);

    const rowHeight = useMemo(() => {
        const totalMargin = (tiling.rows - 1) * MARGIN[1];
        return Math.max(30, (containerHeight - totalMargin) / tiling.rows);
    }, [containerHeight, tiling.rows]);

    if (sortedConnectedCameraIds.length === 0) {
        return (
            <div ref={containerRef} className="camera-grid-empty-state-container camera-grid-container">
                <CameraEmptyState />
            </div>
        );
    }

    return (
        <div ref={containerRef} className="camera-grid-custom mt-1 br-2 camera-grid-container">
            <ReactGridLayout
                width={containerWidth}
                layout={layout}
                gridConfig={{ cols: GRID_COLS, rowHeight, margin: MARGIN, containerPadding: [0, 0] as [number, number] }}
                dragConfig={{ enabled: true }}
                resizeConfig={{ enabled: true }}
                compactor={noCompactor}
                onLayoutChange={handleLayoutChange}
                onDragStart={handleDragStart}
                onDragStop={handleDragStop}
                onResizeStop={handleResizeStop}
            >
                {sortedConnectedCameraIds.map((cameraId) => (
                    <div key={cameraId} className={clsx("camera-cell", isRecording && "recording")}>
                        <CameraGridCell cameraId={cameraId} />
                    </div>
                ))}
            </ReactGridLayout>
        </div>
    );
};
