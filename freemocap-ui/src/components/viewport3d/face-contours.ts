import { Color } from "three";
import {SKELETON_COLORS} from "@/components/viewport3d/skeleton-colors";

/**
 * MediaPipe face mesh contour connections, matching the Python tracker's
 * naming convention: `face.{group}_{raw_mediapipe_index}`.
 *
 * Connection pairs come from mediapipe.python.solutions.face_mesh_connections:
 *   FACEMESH_LIPS, FACEMESH_LEFT_EYE, FACEMESH_RIGHT_EYE,
 *   FACEMESH_LEFT_EYEBROW, FACEMESH_RIGHT_EYEBROW, FACEMESH_FACE_OVAL,
 *   FACEMESH_LEFT_IRIS, FACEMESH_RIGHT_IRIS
 */

interface FaceContourGroup {
    prefix: string;
    connections: [number, number][];
    color: Color;
}

const FACE_CONTOUR_GROUPS: FaceContourGroup[] = [
    {
        prefix: "face.lips",
        color: SKELETON_COLORS.face,
        connections: [
            // Outer lip upper
            [61, 146], [146, 91], [91, 181], [181, 84], [84, 17],
            [17, 314], [314, 405], [405, 321], [321, 375], [375, 291],
            // Outer lip lower
            [61, 185], [185, 40], [40, 39], [39, 37], [37, 0],
            [0, 267], [267, 269], [269, 270], [270, 409], [409, 291],
            // Inner lip upper
            [78, 95], [95, 88], [88, 178], [178, 87], [87, 14],
            [14, 317], [317, 402], [402, 318], [318, 324], [324, 308],
            // Inner lip lower
            [78, 191], [191, 80], [80, 81], [81, 82], [82, 13],
            [13, 312], [312, 311], [311, 310], [310, 415], [415, 308],
        ],
    },
    {
        prefix: "face.left_eye",
        color: SKELETON_COLORS.face,
        connections: [
            [263, 249], [249, 390], [390, 373], [373, 374], [374, 380],
            [380, 381], [381, 382], [382, 362],
            [263, 466], [466, 388], [388, 387], [387, 386], [386, 385],
            [385, 384], [384, 398], [398, 362],
        ],
    },
    {
        prefix: "face.right_eye",
        color: SKELETON_COLORS.face,
        connections: [
            [33, 7], [7, 163], [163, 144], [144, 145], [145, 153],
            [153, 154], [154, 155], [155, 133],
            [33, 246], [246, 161], [161, 160], [160, 159], [159, 158],
            [158, 157], [157, 173], [173, 133],
        ],
    },
    {
        prefix: "face.left_eyebrow",
        color: SKELETON_COLORS.face,
        connections: [
            [276, 283], [283, 282], [282, 295], [295, 285],
            [300, 293], [293, 334], [334, 296], [296, 336],
        ],
    },
    {
        prefix: "face.right_eyebrow",
        color: SKELETON_COLORS.face,
        connections: [
            [46, 53], [53, 52], [52, 65], [65, 55],
            [70, 63], [63, 105], [105, 66], [66, 107],
        ],
    },
    {
        prefix: "face.face_oval",
        color: SKELETON_COLORS.face,
        connections: [
            [10, 338], [338, 297], [297, 332], [332, 284], [284, 251],
            [251, 389], [389, 356], [356, 454], [454, 323], [323, 361],
            [361, 288], [288, 397], [397, 365], [365, 379], [379, 378],
            [378, 400], [400, 377], [377, 152], [152, 148], [148, 176],
            [176, 149], [149, 150], [150, 136], [136, 172], [172, 58],
            [58, 132], [132, 93], [93, 234], [234, 127], [127, 162],
            [162, 21], [21, 54], [54, 103], [103, 67], [67, 109],
            [109, 10],
        ],
    },
    {
        prefix: "face.left_iris",
        color: SKELETON_COLORS.face,
        connections: [
            [474, 475], [475, 476], [476, 477], [477, 474],
        ],
    },
    {
        prefix: "face.right_iris",
        color: SKELETON_COLORS.face,
        connections: [
            [469, 470], [470, 471], [471, 472], [472, 469],
        ],
    },
];

/**
 * Build segment definitions for all face contour groups.
 * Each connection (a, b) becomes a segment from `{prefix}_{a}` to `{prefix}_{b}`.
 */
export function buildFaceContourSegments(): Record<string, { proximal: string; distal: string }> {
    const segments: Record<string, { proximal: string; distal: string }> = {};

    for (const group of FACE_CONTOUR_GROUPS) {
        for (let i = 0; i < group.connections.length; i++) {
            const [a, b] = group.connections[i];
            segments[`${group.prefix}_seg_${i}`] = {
                proximal: `${group.prefix}_${a}`,
                distal: `${group.prefix}_${b}`,
            };
        }
    }

    return segments;
}

/**
 * Build the color array for all face contour segments, in the same
 * order as buildFaceContourSegments produces entries.
 */
export function buildFaceContourColors(): Color[] {
    const colors: Color[] = [];

    for (const group of FACE_CONTOUR_GROUPS) {
        for (let _i = 0; _i < group.connections.length; _i++) {
            colors.push(group.color);
        }
    }

    return colors;
}
