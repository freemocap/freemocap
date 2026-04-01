import { Color } from "three";
import { PointStyle } from "@/components/viewport3d/viewport3d-types";
import { buildFaceContourSegments, buildFaceContourColors } from "@/components/viewport3d/face-contours";
import {SKELETON_COLORS} from "@/components/viewport3d/skeleton-colors";

// Maximum tracked points the instanced mesh can hold
export const MAX_POINTS = 1000;

// Z-axis offset applied to all tracked points to center the skeleton in view
export const Z_OFFSET = -15;

// --- Color palette (matches 2D overlay) ---



// --- Point styling: color + sphere scale per body part ---

export function getPointStyle(name: string): PointStyle {
    // Face landmarks — near-invisible dots, contour lines carry the visual
    if (name.startsWith('face.')) {
        return { color: SKELETON_COLORS.face, scale: 0.02 };
    }

    if (name.startsWith('left_hand.')) {
        return { color: SKELETON_COLORS.leftHand, scale: 0.075 };
    }
    if (name.startsWith('right_hand.')) {
        return { color: SKELETON_COLORS.rightHand, scale: 0.075 };
    }

    // Body — eyes, ears, mouth are small
    if (name.includes('eye') || name.includes('ear') || name.includes('mouth')) {
        const side = name.includes('left') ? SKELETON_COLORS.left
            : name.includes('right') ? SKELETON_COLORS.right
            : SKELETON_COLORS.center;
        return { color: side, scale: 0.125 };
    }

    // Body — fingers at wrist level
    if (name.includes('pinky') || name.includes('index') || name.includes('thumb')) {
        const side = name.includes('left') ? SKELETON_COLORS.left : SKELETON_COLORS.right;
        return { color: side, scale: 0.05 };
    }

    // Body — feet
    if (name.includes('heel') || name.includes('foot_index') || name.includes('ankle')) {
        const side = name.includes('left') ? SKELETON_COLORS.left : SKELETON_COLORS.right;
        return { color: side, scale: 0.3 };
    }

    // Body — major joints (shoulder, elbow, wrist, hip, knee)
    if (name.includes('left')) {
        return { color: SKELETON_COLORS.left, scale: 0.2 };
    }
    if (name.includes('right')) {
        return { color: SKELETON_COLORS.right, scale: 0.2 };
    }

    // Center (nose, etc.)
    return { color: SKELETON_COLORS.center, scale: 0.15 };
}

// --- Segment color determined by segment name ---

function getSegmentColor(segmentName: string): Color {
    if (segmentName.startsWith('left_hand_'))  return SKELETON_COLORS.leftHand;
    if (segmentName.startsWith('right_hand_')) return SKELETON_COLORS.rightHand;
    if (segmentName.startsWith('left'))        return SKELETON_COLORS.left;
    if (segmentName.startsWith('right'))       return SKELETON_COLORS.right;
    return SKELETON_COLORS.center;
}

// --- Hand connection template (MediaPipe hand landmark topology) ---

const HAND_CONNECTIONS: [string, string][] = [
    // Thumb
    ['wrist', 'thumb_cmc'],
    ['thumb_cmc', 'thumb_mcp'],
    ['thumb_mcp', 'thumb_ip'],
    ['thumb_ip', 'thumb_tip'],
    // Index finger
    ['wrist', 'index_finger_mcp'],
    ['index_finger_mcp', 'index_finger_pip'],
    ['index_finger_pip', 'index_finger_dip'],
    ['index_finger_dip', 'index_finger_tip'],
    // Middle finger
    ['wrist', 'middle_finger_mcp'],
    ['middle_finger_mcp', 'middle_finger_pip'],
    ['middle_finger_pip', 'middle_finger_dip'],
    ['middle_finger_dip', 'middle_finger_tip'],
    // Ring finger
    ['wrist', 'ring_finger_mcp'],
    ['ring_finger_mcp', 'ring_finger_pip'],
    ['ring_finger_pip', 'ring_finger_dip'],
    ['ring_finger_dip', 'ring_finger_tip'],
    // Pinky
    ['wrist', 'pinky_mcp'],
    ['pinky_mcp', 'pinky_pip'],
    ['pinky_pip', 'pinky_dip'],
    ['pinky_dip', 'pinky_tip'],
    // Palm
    ['index_finger_mcp', 'middle_finger_mcp'],
    ['middle_finger_mcp', 'ring_finger_mcp'],
    ['ring_finger_mcp', 'pinky_mcp'],
];

function buildHandSegments(handPrefix: string): Record<string, { proximal: string; distal: string }> {
    const segments: Record<string, { proximal: string; distal: string }> = {};
    HAND_CONNECTIONS.forEach(([proximal, distal], i) => {
        segments[`${handPrefix}_seg_${i}`] = {
            proximal: `${handPrefix}.${proximal}`,
            distal: `${handPrefix}.${distal}`,
        };
    });
    return segments;
}

// --- Body + hand segment definitions ---

const BODY_HAND_SEGMENTS: Record<string, { proximal: string; distal: string }> = {
    // Body
    head:               { proximal: "body.left_ear",        distal: "body.right_ear" },
    neck:               { proximal: "head_center",          distal: "neck_center" },
    spine:              { proximal: "neck_center",          distal: "hips_center" },
    right_shoulder:     { proximal: "neck_center",          distal: "body.right_shoulder" },
    left_shoulder:      { proximal: "neck_center",          distal: "body.left_shoulder" },
    right_upper_arm:    { proximal: "body.right_shoulder",  distal: "body.right_elbow" },
    left_upper_arm:     { proximal: "body.left_shoulder",   distal: "body.left_elbow" },
    right_forearm:      { proximal: "body.right_elbow",     distal: "body.right_wrist" },
    left_forearm:       { proximal: "body.left_elbow",      distal: "body.left_wrist" },
    right_hand_body:    { proximal: "body.right_wrist",     distal: "body.right_index" },
    left_hand_body:     { proximal: "body.left_wrist",      distal: "body.left_index" },
    right_pelvis:       { proximal: "hips_center",          distal: "body.right_hip" },
    left_pelvis:        { proximal: "hips_center",          distal: "body.left_hip" },
    right_thigh:        { proximal: "body.right_hip",       distal: "body.right_knee" },
    left_thigh:         { proximal: "body.left_hip",        distal: "body.left_knee" },
    right_shank:        { proximal: "body.right_knee",      distal: "body.right_ankle" },
    left_shank:         { proximal: "body.left_knee",       distal: "body.left_ankle" },
    right_foot:         { proximal: "body.right_ankle",     distal: "body.right_foot_index" },
    left_foot:          { proximal: "body.left_ankle",      distal: "body.left_foot_index" },
    right_heel:         { proximal: "body.right_ankle",     distal: "body.right_heel" },
    left_heel:          { proximal: "body.left_ankle",      distal: "body.left_heel" },
    right_foot_bottom:  { proximal: "body.right_heel",      distal: "body.right_foot_index" },
    left_foot_bottom:   { proximal: "body.left_heel",       distal: "body.left_foot_index" },
    // Hands
    ...buildHandSegments('right_hand'),
    ...buildHandSegments('left_hand'),
};

// Pre-compute body+hand segment colors
const BODY_HAND_COLORS: Color[] = Object.keys(BODY_HAND_SEGMENTS).map(getSegmentColor);

// --- Face contour segments ---

const FACE_SEGMENTS = buildFaceContourSegments();
const FACE_COLORS = buildFaceContourColors();

// --- Combined: body + hands + face contours ---

export const SEGMENT_DEFINITIONS: Record<string, { proximal: string; distal: string }> = {
    ...BODY_HAND_SEGMENTS,
    ...FACE_SEGMENTS,
};

export const MAX_SEGMENTS = Object.keys(SEGMENT_DEFINITIONS).length;

// Colors in matching order: body+hand first, then face contours
export const SEGMENT_COLORS: Color[] = [...BODY_HAND_COLORS, ...FACE_COLORS];