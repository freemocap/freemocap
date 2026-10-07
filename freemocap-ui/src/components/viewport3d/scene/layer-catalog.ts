import { BONE_SIDE_HEX } from "../renderers/RigidBodyBoneInstances";
import { SKELETON_KEYPOINT_COLORS } from "../helpers/skeleton-colors";
import { COLORS } from "../helpers/colors";
import { AXIS_HEX, LAYER_HEX } from "../helpers/layer-colors";
import type { CountedLayerKey, LayerKey } from "../helpers/viewport3d-types";

/**
 * Everything the viewport panel shows about layers, as data: which layers exist, how they are grouped,
 * what they are called, what they look like, and which live count they report.
 *
 * Swatch colors are read from the same tables the renderers draw with, so the legend
 * always matches the scene.
 */

/** How a layer looks in the scene: points, thin lines, or solid bars. */
export type SwatchShape = "dot" | "line" | "bar";

export interface LayerSwatch {
    shape: SwatchShape;
    /** One color, or several side-by-side stripes (e.g. left / center / right). */
    colors: readonly string[];
}

export interface LayerSpec {
    key: LayerKey;
    label: string;
    /** One sentence on what this layer draws. Shown as the row's tooltip. */
    description: string;
    swatch: LayerSwatch | null;
    /** The live count shown next to the label. */
    countKey: CountedLayerKey | null;
    /** Sub-layers, shown indented under this row and disabled while it is off. */
    children: readonly LayerSpec[];
}

export interface LayerGroup {
    id: "model" | "tracking" | "saved" | "balance" | "scene";
    title: string;
    layers: readonly LayerSpec[];
}

const hex = (c: { getHexString: () => string }): string => `#${c.getHexString()}`;

const SIDE_HEX = [BONE_SIDE_HEX.left, BONE_SIDE_HEX.center, BONE_SIDE_HEX.right] as const;
const LANDMARK_SIDE_HEX = [
    hex(SKELETON_KEYPOINT_COLORS.left),
    hex(SKELETON_KEYPOINT_COLORS.center),
    hex(SKELETON_KEYPOINT_COLORS.right),
] as const;

function layer(
    key: LayerKey,
    label: string,
    description: string,
    swatch: LayerSwatch | null,
    countKey: CountedLayerKey | null = null,
    children: readonly LayerSpec[] = [],
): LayerSpec {
    return { key, label, description, swatch, countKey, children };
}

export const LAYER_GROUPS: readonly LayerGroup[] = [
    {
        id: "model",
        title: "Tracked model",
        layers: [
            layer("bones", "Bones",
                "Solid rigid-body segments of the fitted model. Blue = left, red = right, sand = midline.",
                { shape: "bar", colors: SIDE_HEX }),
            layer("boneLines", "Bone lines",
                "Thin lines from each segment's origin to its children's origins.",
                { shape: "line", colors: SIDE_HEX }, "boneLines"),
            layer("landmarks", "Landmarks",
                "Anatomical points on the fitted model (joints, hand and foot points), colored by side.",
                { shape: "dot", colors: LANDMARK_SIDE_HEX }, "landmarks"),
            layer("segmentAxes", "Segment axes",
                "Each segment's local x / y / z axes (red / green / blue) at its origin.",
                { shape: "line", colors: AXIS_HEX }),
            layer("face", "Face outline",
                "Face contour lines.",
                { shape: "line", colors: [hex(COLORS.face)] }, "face"),
        ],
    },
    {
        id: "tracking",
        title: "Tracking input",
        layers: [
            layer("rawKeypoints", "Raw keypoints",
                "Triangulated 3D points straight from the detector, before any model fitting.",
                { shape: "dot", colors: [LAYER_HEX.rawKeypoints] }, "rawKeypoints"),
            layer("mappedKeypoints", "Mapped keypoints",
                "Detector keypoints placed under the model's landmark names, before fitting.",
                { shape: "dot", colors: [LAYER_HEX.mappedKeypoints] }, "mappedKeypoints"),
        ],
    },
    {
        id: "saved",
        title: "Saved fit",
        layers: [
            layer("savedSkeleton", "Saved skeleton",
                "The skeleton stored with this recording's fit.",
                { shape: "bar", colors: [LAYER_HEX.savedSkeleton] }),
            layer("savedSkeletonAxes", "Saved skeleton axes",
                "Each saved segment's local x / y / z axes (red / green / blue).",
                { shape: "line", colors: AXIS_HEX }),
        ],
    },
    {
        id: "balance",
        title: "Balance",
        layers: [
            layer("centerOfMass", "Center of mass",
                "Whole-body center of mass (CoM) and its balance markers.",
                { shape: "dot", colors: [LAYER_HEX.centerOfMass, LAYER_HEX.xcom] }, null, [
                    layer("comMarker", "CoM marker",
                        "Sphere at the 3D center of mass.",
                        { shape: "dot", colors: [LAYER_HEX.centerOfMass] }),
                    layer("comFloorPoint", "Floor point",
                        "The CoM projected straight down onto the floor.",
                        { shape: "dot", colors: [LAYER_HEX.centerOfMass] }),
                    layer("comDropLine", "Drop line",
                        "Vertical line from the CoM down to its floor point.",
                        { shape: "line", colors: [LAYER_HEX.centerOfMass] }),
                    layer("xcom", "XCoM",
                        "Extrapolated center of mass (Hof 2008): where the CoM is heading, given its velocity, drawn on the floor.",
                        { shape: "dot", colors: [LAYER_HEX.xcom] }),
                    layer("xcomLine", "XCoM line",
                        "Floor line from the CoM floor point to the XCoM.",
                        { shape: "line", colors: [LAYER_HEX.xcom] }),
                ]),
        ],
    },
    {
        id: "scene",
        title: "Scene",
        layers: [
            layer("floorGrid", "Floor grid",
                "Floor grid and the world origin axes.",
                null),
            layer("cameras", "Cameras",
                "Calibrated camera positions and viewing directions.",
                { shape: "bar", colors: [LAYER_HEX.cameras] }, "cameras"),
        ],
    },
];
