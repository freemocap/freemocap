import {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import type {Layout, LayoutItem} from 'react-grid-layout';
import {
    type Tiling,
    computeOptimalTiling,
    tilingFromColumns,
    buildLayout,
} from '@/utils/gridTiling';

// ── Defaults ────────────────────────────────────────────────────────────────

const DEFAULT_GRID_COLS = 12;
const DEFAULT_MARGIN: [number, number] = [4, 4];
const DEFAULT_MIN_ROW_HEIGHT = 30;
const DEFAULT_WIDTH = 800;
const DEFAULT_HEIGHT = 600;

// ── Types ───────────────────────────────────────────────────────────────────

export interface UseGridLayoutOptions {
    /** Ordered list of unique IDs for the items to arrange in the grid. */
    itemIds: string[];
    /** Number of abstract grid columns. Default: 12 */
    gridCols?: number;
    /** Gap between items in pixels [horizontal, vertical]. Default: [4, 4] */
    margin?: [number, number];
    /** null = auto-optimize tiling, number = force N columns. Default: null */
    manualColumns?: number | null;
    /** Increment to force a full layout reset. Default: 0 */
    resetKey?: number;
    /** If true, observe the PARENT of containerRef (avoids ResizeObserver feedback
     *  loops when the container has percentage dimensions). Default: true */
    measureParent?: boolean;
    /** Minimum row height in pixels. Default: 30 */
    minRowHeight?: number;
    /** Additional dependencies that trigger user-override reset. When any change,
     *  drag/resize overrides are discarded. */
    extraResetDeps?: React.DependencyList;
}

export interface UseGridLayoutResult {
    /** Ref to attach to the container element whose dimensions define the grid area. */
    containerRef: React.RefObject<HTMLDivElement | null>;
    /** Current measured width of the container in pixels. */
    width: number;
    /** Computed tiling (cols, rows). */
    tiling: Tiling;
    /** Resolved layout items (user override or auto-computed). */
    layout: LayoutItem[];
    /** Event handlers to spread onto <ReactGridLayout>. */
    gridHandlers: {
        onLayoutChange: (layout: Layout) => void;
        onDragStart: () => void;
        onDragStop: (layout: Layout, oldItem: LayoutItem | null, newItem: LayoutItem | null) => void;
        onResizeStop: (layout: Layout) => void;
    };
    /** Pre-built gridConfig for <ReactGridLayout>. */
    gridConfig: {
        cols: number;
        rowHeight: number;
        margin: [number, number];
        containerPadding: [number, number];
    };
}

// ── Hook ────────────────────────────────────────────────────────────────────

export function useGridLayout(options: UseGridLayoutOptions): UseGridLayoutResult {
    const {
        itemIds,
        gridCols = DEFAULT_GRID_COLS,
        margin = DEFAULT_MARGIN,
        manualColumns = null,
        resetKey = 0,
        measureParent = true,
        minRowHeight = DEFAULT_MIN_ROW_HEIGHT,
        extraResetDeps = [],
    } = options;

    // ── Container measurement ───────────────────────────────────────────────

    const containerRef = useRef<HTMLDivElement>(null);
    const [width, setWidth] = useState(DEFAULT_WIDTH);
    const [height, setHeight] = useState(DEFAULT_HEIGHT);

    useEffect(() => {
        const el = containerRef.current;
        const target = measureParent ? el?.parentElement : el;
        if (!target) return;

        const measure = () => {
            const rect = target.getBoundingClientRect();
            setWidth(rect.width);
            setHeight(rect.height);
        };

        measure();
        const observer = new ResizeObserver(() => measure());
        observer.observe(target);
        return () => observer.disconnect();
    }, [measureParent]);

    // ── Tiling computation ──────────────────────────────────────────────────

    const prevTilingRef = useRef<Tiling>({cols: 1, rows: 1});
    const tiling = useMemo(() => {
        const candidate = manualColumns !== null
            ? tilingFromColumns(itemIds.length, manualColumns)
            : computeOptimalTiling(itemIds.length, width, height, margin);
        const prev = prevTilingRef.current;
        if (candidate.cols === prev.cols && candidate.rows === prev.rows) {
            return prev;
        }
        prevTilingRef.current = candidate;
        return candidate;
    }, [itemIds.length, width, height, manualColumns, margin]);

    // ── Layout state ────────────────────────────────────────────────────────

    // null = auto-compute; non-null = user has dragged or resized
    const [userLayout, setUserLayout] = useState<LayoutItem[] | null>(null);

    // Reset user overrides when the auto layout would change
    useEffect(() => {
        setUserLayout(null);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [itemIds, tiling, resetKey, ...extraResetDeps]);

    const layout = useMemo(() => {
        if (userLayout !== null) return userLayout;
        return buildLayout(itemIds, tiling, gridCols);
    }, [itemIds, tiling, gridCols, userLayout]);

    // ── Row height & grid config ────────────────────────────────────────────

    const rowHeight = useMemo(() => {
        const totalMargin = (tiling.rows - 1) * margin[1];
        return Math.max(minRowHeight, (height - totalMargin) / tiling.rows);
    }, [height, tiling.rows, margin, minRowHeight]);

    const gridConfig = useMemo(() => ({
        cols: gridCols,
        rowHeight,
        margin,
        containerPadding: [0, 0] as [number, number],
    }), [gridCols, rowHeight, margin]);

    // ── Drag / resize handlers ──────────────────────────────────────────────

    const layoutBeforeDragRef = useRef<LayoutItem[]>([]);

    const handleDragStart = useCallback(() => {
        layoutBeforeDragRef.current = layout;
    }, [layout]);

    const handleDragStop = useCallback((
        _newLayout: Layout,
        _oldItem: LayoutItem | null,
        newItem: LayoutItem | null,
    ) => {
        if (!newItem) return;
        const preDrag = layoutBeforeDragRef.current;
        const draggedBefore = preDrag.find((l) => l.i === newItem.i);
        if (!draggedBefore) return;

        const swapTarget = preDrag.find((l) => {
            if (l.i === newItem.i) return false;
            return newItem.x < l.x + l.w && newItem.x + newItem.w > l.x
                && newItem.y < l.y + l.h && newItem.y + newItem.h > l.y;
        });

        if (swapTarget) {
            setUserLayout(preDrag.map((l) => {
                if (l.i === newItem.i) return {...l, x: swapTarget.x, y: swapTarget.y};
                if (l.i === swapTarget.i) return {...l, x: draggedBefore.x, y: draggedBefore.y};
                return l;
            }));
        } else {
            const maxX = gridCols - newItem.w;
            const maxY = tiling.rows - newItem.h;
            setUserLayout(preDrag.map((l) => {
                if (l.i === newItem.i) {
                    return {
                        ...l,
                        x: Math.max(0, Math.min(newItem.x, maxX)),
                        y: Math.max(0, Math.min(newItem.y, maxY)),
                    };
                }
                return l;
            }));
        }
    }, [tiling.rows, gridCols]);

    const handleResizeStop = useCallback((newLayout: Layout) => {
        setUserLayout([...newLayout]);
    }, []);

    const handleLayoutChange = useCallback((_layout: Layout) => {}, []);

    const gridHandlers = useMemo(() => ({
        onLayoutChange: handleLayoutChange,
        onDragStart: handleDragStart,
        onDragStop: handleDragStop,
        onResizeStop: handleResizeStop,
    }), [handleLayoutChange, handleDragStart, handleDragStop, handleResizeStop]);

    return {
        containerRef,
        width,
        tiling,
        layout,
        gridHandlers,
        gridConfig,
    };
}
