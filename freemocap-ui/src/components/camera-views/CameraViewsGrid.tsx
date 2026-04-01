import React, { useState, useCallback, useRef, useEffect, useMemo } from "react";
import { Box, keyframes } from "@mui/material";
import ReactGridLayout, { noCompactor } from "react-grid-layout";
import type { Layout, LayoutItem } from "react-grid-layout";
import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";
import { CameraView } from "./CameraView";
import { useServer } from "@/services/server/ServerContextProvider";
import { useTranslation } from "react-i18next";
import { useAppSelector } from "@/store/hooks";
import { selectConnectedCameras } from "@/store/slices/cameras/cameras-selectors";

const recordingBorderPulse = keyframes`
    0% { border-color: #ff2020; box-shadow: 0 0 4px rgba(255, 32, 32, 0.4); }
    50% { border-color: #aa1010; box-shadow: 0 0 8px rgba(255, 32, 32, 0.15); }
    100% { border-color: #ff2020; box-shadow: 0 0 4px rgba(255, 32, 32, 0.4); }
`;

/** Number of abstract grid columns. More columns = finer positioning granularity. */
const GRID_COLS = 12;
const MARGIN: [number, number] = [4, 4];

interface Tiling {
    cols: number;
    rows: number;
}

/**
 * Try every possible column count for N cameras within the given container
 * dimensions and return the one that maximizes total pixel area used.
 */
function computeOptimalTiling(
    n: number,
    containerWidth: number,
    containerHeight: number,
): Tiling {
    if (n === 0) return { cols: 1, rows: 1 };
    if (n === 1) return { cols: 1, rows: 1 };

    let bestCols = 1;
    let bestArea = 0;

    for (let cols = 1; cols <= n; cols++) {
        const rows = Math.ceil(n / cols);
        const cellW = (containerWidth - MARGIN[0] * (cols - 1)) / cols;
        const cellH = (containerHeight - MARGIN[1] * (rows - 1)) / rows;

        if (cellW < 80 || cellH < 60) continue;

        const totalArea = n * cellW * cellH;
        if (totalArea > bestArea) {
            bestArea = totalArea;
            bestCols = cols;
        }
    }

    return { cols: bestCols, rows: Math.ceil(n / bestCols) };
}

/**
 * Build a tiling from a manual column count.
 */
function tilingFromColumns(n: number, cols: number): Tiling {
    if (n === 0) return { cols: 1, rows: 1 };
    const clamped = Math.max(1, Math.min(cols, n));
    return { cols: clamped, rows: Math.ceil(n / clamped) };
}

/**
 * Build a react-grid-layout layout from a tiling.
 */
function buildLayout(cameraIds: string[], tiling: Tiling): LayoutItem[] {
    const n = cameraIds.length;
    if (n === 0) return [];

    const colSpan = Math.floor(GRID_COLS / tiling.cols);

    return cameraIds.map((id, i) => ({
        i: id,
        x: (i % tiling.cols) * colSpan,
        y: Math.floor(i / tiling.cols),
        w: colSpan,
        h: 1,
        minW: 1,
        minH: 1,
    }));
}

interface CameraViewsGridProps {
    /** null = auto-optimize, number = manual column count */
    manualColumns: number | null;
    /** Increment to force a layout reset */
    resetKey: number;
}

export const CameraViewsGrid: React.FC<CameraViewsGridProps> = ({ manualColumns, resetKey }) => {
    const { connectedCameraIds } = useServer();
    const { t } = useTranslation();
    const isRecording = useAppSelector(state => state.recording.isRecording);
    const containerRef = useRef<HTMLDivElement>(null);
    const [containerWidth, setContainerWidth] = useState<number>(800);
    const [containerHeight, setContainerHeight] = useState<number>(600);

    // Measure the container's parent to avoid feedback loops
    useEffect(() => {
        const el = containerRef.current?.parentElement;
        if (!el) return;

        const measure = () => {
            const rect = el.getBoundingClientRect();
            setContainerWidth(rect.width);
            setContainerHeight(rect.height);
        };

        measure();
        const observer = new ResizeObserver(() => measure());
        observer.observe(el);
        return () => observer.disconnect();
    }, []);

    // Watch camera configs for rotation/resolution changes
    const connectedCameras = useAppSelector(selectConnectedCameras);
    const configFingerprint = useMemo(() => {
        return connectedCameras
            .map((cam) => {
                const cfg = cam.actualConfig;
                return `${cam.id}:${cfg.rotation}:${cfg.resolution.width}x${cfg.resolution.height}`;
            })
            .join("|");
    }, [connectedCameras]);

    // Compute tiling: manual column count overrides auto-optimal.
    // Stabilized with a ref to prevent flip-flop.
    const prevTilingRef = useRef<Tiling>({ cols: 1, rows: 1 });
    const tiling = useMemo(() => {
        const candidate = manualColumns !== null
            ? tilingFromColumns(connectedCameraIds.length, manualColumns)
            : computeOptimalTiling(connectedCameraIds.length, containerWidth, containerHeight);
        const prev = prevTilingRef.current;
        if (candidate.cols === prev.cols && candidate.rows === prev.rows) {
            return prev;
        }
        prevTilingRef.current = candidate;
        return candidate;
    }, [connectedCameraIds.length, containerWidth, containerHeight, manualColumns]);

    const [layout, setLayout] = useState<LayoutItem[]>(() =>
        buildLayout(connectedCameraIds, tiling),
    );

    // Re-tile when cameras, tiling, config, or reset changes
    useEffect(() => {
        setLayout(buildLayout(connectedCameraIds, tiling));
    }, [connectedCameraIds, tiling, resetKey, configFingerprint]);

    // Snapshot layout before drag for swap detection
    const layoutBeforeDragRef = useRef<LayoutItem[]>(layout);

    const handleDragStart = useCallback(() => {
        layoutBeforeDragRef.current = layout;
    }, [layout]);

    const handleDragStop = useCallback((_newLayout: Layout, _oldItem: LayoutItem | null, newItem: LayoutItem | null) => {
        if (!newItem) return;
        const preDrag = layoutBeforeDragRef.current;
        const draggedBefore = preDrag.find((l) => l.i === newItem.i);
        if (!draggedBefore) return;

        // Check if we landed on another item
        const swapTarget = preDrag.find((l) => {
            if (l.i === newItem.i) return false;
            const overlapX = newItem.x < l.x + l.w && newItem.x + newItem.w > l.x;
            const overlapY = newItem.y < l.y + l.h && newItem.y + newItem.h > l.y;
            return overlapX && overlapY;
        });

        if (swapTarget) {
            const swapped = preDrag.map((l) => {
                if (l.i === newItem.i) {
                    return { ...l, x: swapTarget.x, y: swapTarget.y };
                }
                if (l.i === swapTarget.i) {
                    return { ...l, x: draggedBefore.x, y: draggedBefore.y };
                }
                return l;
            });
            setLayout(swapped);
        } else {
            // Dropped in empty space — clamp to grid bounds
            const maxX = GRID_COLS - newItem.w;
            const maxY = tiling.rows - newItem.h;
            const updated = preDrag.map((l) => {
                if (l.i === newItem.i) {
                    return {
                        ...l,
                        x: Math.max(0, Math.min(newItem.x, maxX)),
                        y: Math.max(0, Math.min(newItem.y, maxY)),
                    };
                }
                return l;
            });
            setLayout(updated);
        }
    }, [tiling.rows]);

    const handleLayoutChange = useCallback((_newLayout: Layout) => {}, []);

    const handleResizeStop = useCallback((newLayout: Layout) => {
        setLayout([...newLayout]);
    }, []);

    const rowHeight = useMemo(() => {
        const totalMargin = (tiling.rows - 1) * MARGIN[1];
        return Math.max(30, (containerHeight - totalMargin) / tiling.rows);
    }, [containerHeight, tiling.rows]);

    if (connectedCameraIds.length === 0) {
        return (
            <Box
                ref={containerRef}
                sx={{
                    height: "100%",
                    width: "100%",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "text.secondary",
                    fontSize: "1.2rem",
                    padding: 4,
                    textAlign: "center",
                }}
            >
                <div>
                    <div>{t("noCamerasConnected")}</div>
                    <div style={{ fontSize: "0.9rem", marginTop: "0.5rem" }}>
                        {t("waitingForCameraStreams")}
                    </div>
                </div>
            </Box>
        );
    }

    return (
        <Box
            ref={containerRef}
            sx={{
                position: "relative",
                width: "100%",
                height: "100%",
                minHeight: 300,
                overflow: "hidden",
                "& .react-grid-placeholder": {
                    backgroundColor: "primary.main",
                    opacity: 0.15,
                    borderRadius: "4px",
                },
                "& .react-grid-item > .react-resizable-handle": {
                    zIndex: 10,
                    opacity: 0.4,
                    transition: "opacity 0.2s ease",
                },
                "& .react-grid-item:hover > .react-resizable-handle": {
                    opacity: 1,
                },
                "& .react-grid-item > .react-resizable-handle::after": {
                    width: "10px",
                    height: "10px",
                    right: "4px",
                    bottom: "4px",
                    borderRight: "2px solid rgba(255, 255, 255, 0.5)",
                    borderBottom: "2px solid rgba(255, 255, 255, 0.5)",
                },
            }}
        >
            <ReactGridLayout
                width={containerWidth}
                layout={layout}
                gridConfig={{
                    cols: GRID_COLS,
                    rowHeight,
                    margin: MARGIN,
                    containerPadding: [0, 0] as [number, number],
                }}
                dragConfig={{ enabled: true }}
                resizeConfig={{ enabled: true }}
                compactor={noCompactor}
                onLayoutChange={handleLayoutChange}
                onDragStart={handleDragStart}
                onDragStop={handleDragStop}
                onResizeStop={handleResizeStop}
            >
                {connectedCameraIds.map((cameraId) => (
                    <Box
                        key={cameraId}
                        sx={{
                            overflow: "hidden",
                            borderRadius: "4px",
                            border: isRecording
                                ? "2px solid #ff2020"
                                : "1px solid rgba(255,255,255,0.15)",
                            transition: "border 0.3s ease, box-shadow 0.3s ease",
                            ...(isRecording && {
                                animation: `${recordingBorderPulse} 3s infinite ease-in-out`,
                            }),
                        }}
                    >
                        <CameraView cameraId={cameraId} />
                    </Box>
                ))}
            </ReactGridLayout>
        </Box>
    );
};
