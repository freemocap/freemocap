import type {LayoutItem} from 'react-grid-layout';

export interface Tiling {
    cols: number;
    rows: number;
}

/**
 * Heuristic for preferred column count based on camera/video count.
 * Mirrors the "old version" logic that gives human-friendly layouts.
 * - 1 item → 1 column
 * - 2–4 items → 2 columns
 * - 5–9 items → 3 columns
 * - 10+ items → 4 columns
 */
export function getPreferredColumns(n: number): number {
    if (n <= 1) return 1;
    if (n <= 4) return 2;
    if (n <= 9) return 3;
    return 4;
}

/**
 * Compute optimal tiling that maximizes visible area while preferring
 * square-ish cells, balanced rows, and human-friendly column counts.
 *
 * @param n               Number of items
 * @param containerWidth  Available pixel width
 * @param containerHeight Available pixel height
 * @param margin          [x, y] gap between items in pixels
 */
export function computeOptimalTiling(
    n: number,
    containerWidth: number,
    containerHeight: number,
    margin: [number, number],
): Tiling {
    if (n === 0) return {cols: 1, rows: 1};
    if (n === 1) return {cols: 1, rows: 1};

    const preferredCols = getPreferredColumns(n);

    const sqrtN = Math.sqrt(n);
    const idealCols = Math.round(sqrtN);

    const minCols = Math.max(1, Math.floor(sqrtN) - 1);
    const maxCols = Math.min(n, Math.ceil(sqrtN) + 2, preferredCols + 1);

    let bestCols = preferredCols;
    let bestScore = -Infinity;

    for (let cols = minCols; cols <= maxCols; cols++) {
        const rows = Math.ceil(n / cols);
        const cellW = (containerWidth - margin[0] * (cols - 1)) / cols;
        const cellH = (containerHeight - margin[1] * (rows - 1)) / rows;

        if (cellW < 80 || cellH < 60) continue;

        // Maximize total area
        const totalArea = n * cellW * cellH;

        // Prefer cells closer to square via log-aspect-ratio penalty
        const aspectRatio = cellW / cellH;
        const aspectPenalty = Math.abs(Math.log(aspectRatio)) * 0.3;

        // Penalize uneven distribution across rows
        const itemsInLastRow = n % cols || cols;
        const balancePenalty = ((cols - itemsInLastRow) / cols) * 0.5;

        // Combined score: maximize area, minimize penalties
        const score = totalArea * (1 - aspectPenalty - balancePenalty);

        // Bonus for matching the preferred column count
        const preferredBonus = cols === preferredCols ? totalArea * 0.1 : 0;

        if (score + preferredBonus > bestScore) {
            bestScore = score + preferredBonus;
            bestCols = cols;
        }
    }

    return {cols: bestCols, rows: Math.ceil(n / bestCols)};
}

/**
 * Build a tiling from a manual column count.
 */
export function tilingFromColumns(n: number, cols: number): Tiling {
    if (n === 0) return {cols: 1, rows: 1};
    const clamped = Math.max(1, Math.min(cols, n));
    return {cols: clamped, rows: Math.ceil(n / clamped)};
}

/**
 * Build a react-grid-layout layout from a tiling and item IDs.
 */
export function buildLayout(ids: string[], tiling: Tiling, gridCols: number): LayoutItem[] {
    if (ids.length === 0) return [];

    const colSpan = Math.floor(gridCols / tiling.cols);

    return ids.map((id, i) => ({
        i: id,
        x: (i % tiling.cols) * colSpan,
        y: Math.floor(i / tiling.cols),
        w: colSpan,
        h: 1,
        minW: 1,
        minH: 1,
    }));
}
