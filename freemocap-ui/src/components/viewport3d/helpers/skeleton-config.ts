import {Color} from "three";
import {SKELETON_KEYPOINT_COLORS} from "@/components/viewport3d/helpers/skeleton-colors";
import {PointStyle} from "@/components/viewport3d/helpers/viewport3d-types";



type PointClass = 'face' | 'left_hand' | 'right_hand' | 'left' | 'right' | 'center';

const classifyCache = new Map<string, PointClass>();

export function classifyPointName(name: string): PointClass {
    const cached = classifyCache.get(name);
    if (cached !== undefined) return cached;
    const lc = name.toLowerCase();
    const left = lc.includes('left') || lc.endsWith('.l');
    const right = lc.includes('right') || lc.endsWith('.r');
    const handPart = /hand|thumb|index|middle|ring|pinky|finger|little/.test(lc);
    let result: PointClass;
    if (lc.startsWith('face') || lc.includes('.face') || /^face[._-]/.test(lc)) result = 'face';
    else if (handPart && left) result = 'left_hand';
    else if (handPart && right) result = 'right_hand';
    else if (left) result = 'left';
    else if (right) result = 'right';
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
            color = hinted ?? SKELETON_KEYPOINT_COLORS.face;
            scale = 0.015;
            break;
        case 'left_hand':
            color = hinted ?? SKELETON_KEYPOINT_COLORS.leftHand;
            scale = 0.025;
            break;
        case 'right_hand':
            color = hinted ?? SKELETON_KEYPOINT_COLORS.rightHand;
            scale = 0.025;
            break;
        case 'left':
            color = hinted ?? SKELETON_KEYPOINT_COLORS.left;
            scale = sizeForBodyPoint(name);
            break;
        case 'right':
            color = hinted ?? SKELETON_KEYPOINT_COLORS.right;
            scale = sizeForBodyPoint(name);
            break;
        default:
            color = hinted ?? SKELETON_KEYPOINT_COLORS.center;
            scale = sizeForBodyPoint(name);
    }

    return {color, scale};
}

function sizeForBodyPoint(name: string): number {
    const lc = name.toLowerCase();
    if (lc.includes('eye') || lc.includes('ear') || lc.includes('mouth') || lc.includes('nose')) return 0.08;
    if (lc.includes('heel') || lc.includes('foot') || lc.includes('toe') || lc.includes('ankle')) return 0.12;
    if (lc.includes('pinky') || lc.includes('index') || lc.includes('thumb')) return 0.03;
    return 0.1;
}
