/**
 * Height policy for the left sidebar's vertically resizable sections.
 *
 * Growable sections (the camera list while streaming, the recording browser in
 * playback) are the sidebar's primary content: they keep a guaranteed floor and absorb
 * all spare height. Every other section prefers its natural content height, but only
 * within the budget left after that floor. When content does not fit, the tallest
 * sections are trimmed first and scroll internally; they never push the cameras away.
 */

/** Growable floor: the camera header rows (backend, count and connect actions) plus two
 *  52 px camera rows, with room for the header to wrap in a narrow sidebar. */
export const GROWABLE_MIN_PX = 220;
/** On a very short sidebar the growable floor takes at most this share of the height. */
export const GROWABLE_MAX_FLOOR_SHARE = 0.75;
/** Smallest height a non-growable section is laid out with or dragged to (its first row). */
export const SECTION_MIN_PX = 48;

export interface SectionPlanInput {
    sections: readonly string[];
    growable: ReadonlySet<string>;
    /** Natural content height (px) of each non-growable section; absent until measured. */
    contentPx: Readonly<Partial<Record<string, number>>>;
    /** Height shared by the section panels (px), excluding dividers; 0 when unknown. */
    availablePx: number;
}

export interface SectionPlan {
    /** Panel sizes in percent, in `sections` order, summing to 100. */
    sizes: number[];
    /** Panel minimum sizes in percent; each is at most the matching size. */
    minSizes: number[];
}

const total = (values: readonly number[]) => values.reduce((sum, value) => sum + value, 0);
const clamp = (value: number, low: number, high: number) => Math.min(high, Math.max(low, value));

/** Before the sidebar has been measured: a valid layout that still favours growable sections. */
function unmeasuredPlan(sections: readonly string[], growable: ReadonlySet<string>): SectionPlan {
    const growableCount = sections.filter(id => growable.has(id)).length;
    const fixedEach = growableCount === 0 ? 100 / sections.length : 12;
    const growableEach = growableCount === 0 ? 0 : (100 - fixedEach * (sections.length - growableCount)) / growableCount;
    return {
        sizes: sections.map(id => growable.has(id) ? growableEach : fixedEach),
        minSizes: sections.map(id => growable.has(id) ? Math.min(8, growableEach) : Math.min(4, fixedEach)),
    };
}

/**
 * Water-filling: every section keeps its preferred height when all fit; otherwise a
 * common cap trims the tallest first, never below a section's floor. Only when even the
 * floors exceed the budget are they scaled down together.
 */
function fitWithinBudget(preferred: readonly number[], floors: readonly number[], budget: number): number[] {
    if (total(preferred) <= budget) return [...preferred];
    const floorTotal = total(floors);
    if (floorTotal >= budget) return floors.map(floor => floorTotal > 0 ? floor * budget / floorTotal : 0);
    const fitted = (cap: number) => preferred.map((height, index) => clamp(cap, floors[index], height));
    let low = 0;
    let high = Math.max(...preferred);
    for (let iteration = 0; iteration < 60; iteration++) {
        const cap = (low + high) / 2;
        if (total(fitted(cap)) > budget) high = cap;
        else low = cap;
    }
    return fitted(low);
}

export function planSidebarSections({sections, growable, contentPx, availablePx}: SectionPlanInput): SectionPlan {
    if (sections.length === 0) return {sizes: [], minSizes: []};
    if (!(availablePx > 0)) return unmeasuredPlan(sections, growable);

    const toPct = (heightPx: number) => heightPx / availablePx * 100;
    const fixedIds = sections.filter(id => !growable.has(id));
    const growableCount = sections.length - fixedIds.length;

    const preferredPx = fixedIds.map(id => Math.max(0, contentPx[id] ?? SECTION_MIN_PX));
    const floorPx = preferredPx.map(height => Math.min(height, SECTION_MIN_PX));
    const growableFloorPx = growableCount === 0
        ? 0
        : Math.min(GROWABLE_MIN_PX, availablePx * GROWABLE_MAX_FLOOR_SHARE / growableCount);
    const fixedPx = fitWithinBudget(preferredPx, floorPx, availablePx - growableFloorPx * growableCount);

    // Spare height goes to the growable sections, or to the last section if there are none.
    const sparePx = availablePx - total(fixedPx);
    if (growableCount === 0) fixedPx[fixedPx.length - 1] += sparePx;
    const fixedPct = fixedPx.map(toPct);
    const growablePct = growableCount === 0 ? 0 : (100 - total(fixedPct)) / growableCount;

    const sizes: number[] = [];
    const minSizes: number[] = [];
    for (const id of sections) {
        const fixedIndex = fixedIds.indexOf(id);
        if (fixedIndex === -1) {
            sizes.push(growablePct);
            minSizes.push(Math.min(toPct(growableFloorPx), growablePct));
        } else {
            sizes.push(fixedPct[fixedIndex]);
            minSizes.push(Math.min(toPct(floorPx[fixedIndex]), fixedPct[fixedIndex]));
        }
    }
    return {sizes, minSizes};
}
