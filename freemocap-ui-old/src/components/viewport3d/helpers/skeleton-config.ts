import {Color} from "three";
import {buildFaceContourColors, buildFaceContourSegments} from "@/components/viewport3d/helpers/face-contours";
import {SKELETON_COLORS} from "@/components/viewport3d/helpers/skeleton-colors";
import {PointStyle} from "@/components/viewport3d/helpers/viewport3d-types";
import {TrackedObjectDefinition} from "@/services/server/server-helpers/tracked-object-definition";



type PointClass = 'face' | 'left_hand' | 'right_hand' | 'left' | 'right' | 'center' | 'aruco';

const classifyCache = new Map<string, PointClass>();

export function classifyPointName(name: string): PointClass {
    const cached = classifyCache.get(name);
    if (cached !== undefined) return cached;
    const lc = name.toLowerCase();
    let result: PointClass;
    if (lc.startsWith('face') || lc.includes('.face') || /^face[._-]/.test(lc)) result = 'face';
    else if (lc.startsWith('arucomarkercorner')) result = 'aruco';
    else if (lc.includes('left_hand')) result = 'left_hand';
    else if (lc.includes('right_hand')) result = 'right_hand';
    else if (lc.includes('left')) result = 'left';
    else if (lc.includes('right')) result = 'right';
    else result = 'center';
    classifyCache.set(name, result);
    return result;
}

// --- Point styling: color + sphere scale per body part ----------------------

// Accepts pre-built Color objects (keyed by point name) so callers in render
// loops can avoid allocating a new Color on every frame.
export function getPointStyle(
    name: string,
    colorHints?: Record<string, Color>,
): PointStyle {
    const hinted = colorHints?.[name];
    const klass = classifyPointName(name);

    let color: Color;
    let scale: number;

    switch (klass) {
        case 'face':
            color = hinted ?? SKELETON_COLORS.face;
            scale = 0.02;
            break;
        case 'left_hand':
            color = hinted ?? SKELETON_COLORS.leftHand;
            scale = 0.075;
            break;
        case 'right_hand':
            color = hinted ?? SKELETON_COLORS.rightHand;
            scale = 0.075;
            break;
        case 'left':
            color = hinted ?? SKELETON_COLORS.left;
            scale = sizeForBodyPoint(name);
            break;
        case 'right':
            color = hinted ?? SKELETON_COLORS.right;
            scale = sizeForBodyPoint(name);
            break;
        case 'aruco':
            color = hinted ?? SKELETON_COLORS.aruco;
            scale = 0.08;
            break;
        default:
            color = hinted ?? SKELETON_COLORS.center;
            scale = sizeForBodyPoint(name);
    }

    return {color, scale};
}

function sizeForBodyPoint(name: string): number {
    const lc = name.toLowerCase();
    if (lc.includes('eye') || lc.includes('ear') || lc.includes('mouth') || lc.includes('nose')) return 0.125;
    if (lc.includes('heel') || lc.includes('foot') || lc.includes('toe') || lc.includes('ankle')) return 0.3;
    if (lc.includes('pinky') || lc.includes('index') || lc.includes('thumb')) return 0.05;
    return 0.2;
}

// --- Segment color: picked from the more specific of the two endpoints ------

export function getSegmentColor(
    proximal: string,
    distal: string,
    colorHints?: Record<string, string>,
): Color {
    // If either endpoint has a hint, use it.
    const hinted = colorHints?.[proximal] ?? colorHints?.[distal];
    if (hinted) return new Color(hinted);

    const pk = classifyPointName(proximal);
    const dk = classifyPointName(distal);
    // Prefer the more specific classification.
    const rank: Record<string, number> = {
        face: 5, left_hand: 4, right_hand: 4, left: 3, right: 3, aruco: 2, center: 1,
    };
    const best = (rank[pk] ?? 0) >= (rank[dk] ?? 0) ? pk : dk;
    switch (best) {
        case 'face': return SKELETON_COLORS.face;
        case 'left_hand': return SKELETON_COLORS.leftHand;
        case 'right_hand': return SKELETON_COLORS.rightHand;
        case 'left': return SKELETON_COLORS.left;
        case 'right': return SKELETON_COLORS.right;
        case 'aruco': return SKELETON_COLORS.aruco;
        default: return SKELETON_COLORS.center;
    }
}

// --- Segment shape -----------------------------------------------------------

export interface Segment {
    proximal: string;
    distal: string;
}

export interface SegmentBundle {
    segments: Segment[];
    colors: Color[];
}

/**
 * Build renderable segments from a tracker schema.
 *
 * Connections come straight from the schema's `connections` list. Face
 * contours are optionally appended when the schema advertises face
 * landmarks — this bridges the current MediaPipe-native face-contour helper
 * until face YAMLs ship their own contour data.
 */
export function buildSegmentsFromSchema(
    def: TrackedObjectDefinition | null | undefined,
): SegmentBundle {
    const segments: Segment[] = [];
    const colors: Color[] = [];

    if (def) {
        for (const [a, b] of def.connections) {
            segments.push({proximal: a, distal: b});
            colors.push(getSegmentColor(a, b, def.color_hints));
        }

        // If the schema includes face landmarks (by name-class), layer the
        // legacy MediaPipe face contours on top.
        const hasFace = def.tracked_points.some(n => classifyPointName(n) === 'face');
        if (hasFace) {
            const faceSegs = buildFaceContourSegments();
            const faceCols = buildFaceContourColors();
            for (const key of Object.keys(faceSegs)) {
                segments.push(faceSegs[key]);
            }
            colors.push(...faceCols);
        }
    }

    return {segments, colors};
}

// Extra capacity beyond the schema's segments — charuco grid connections are
// computed in ConnectionRenderer and need their own slots.
export const MAX_SEGMENT_EXTRAS = 800;
