/**
 * The one table of per-layer identity colors in the 3D viewport.
 *
 * Every renderer that draws a layer in a single color reads it from here, and the
 * viewport panel reads the same values for its legend swatches — so a swatch can never
 * disagree with what the layer actually draws.
 *
 * Layers colored by body side (bones, bone lines, landmarks) take their palette from
 * BONE_SIDE_HEX / SKELETON_KEYPOINT_COLORS; their swatches are derived from those.
 */
export const LAYER_HEX = {
    /** Raw triangulated detector output: neutral white, so it never reads as model output. */
    rawKeypoints: "#f2f2f2",
    /** Detector points renamed onto the model's landmark names: violet, used nowhere else. */
    mappedKeypoints: "#b388ff",
    /** Calibrated camera bodies and frustums. */
    cameras: "#08855e",
    /** Center-of-mass marker, floor point and drop line. */
    centerOfMass: "#ffffff",
    /** Extrapolated center of mass and its floor line. */
    xcom: "#ffaa00",
} as const;

/** Segment-axis triad colors, x / y / z. */
export const AXIS_HEX: readonly [string, string, string] = ["#ff4d40", "#59ff4d", "#4d8cff"];

/** "#rrggbb" → [r, g, b] in 0..1, written straight into vertex-color buffers (no color-space conversion). */
export function hexToRgb01(hex: string): readonly [number, number, number] {
    if (!/^#[0-9a-fA-F]{6}$/.test(hex)) throw new Error(`Expected a #rrggbb color, got "${hex}"`);
    const value = Number.parseInt(hex.slice(1), 16);
    return [((value >> 16) & 0xff) / 255, ((value >> 8) & 0xff) / 255, (value & 0xff) / 255];
}
