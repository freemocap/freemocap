import { Color } from "three";

export const COLORS = {
    // Keypoints - raw are dimmer/smaller, filtered are brighter/larger
    raw:            new Color("#CCC"),
    filtered:       new Color("#44FF88"),
    // Skeleton (FABRIK-fitted canonical) — white stands out from red/blue connections
    skeleton:       new Color("#FFFFFF"),

    // Face
    face:           new Color("#FFD700"),
    // Utility
    hidden:         new Color("#000000"),
} as const;
