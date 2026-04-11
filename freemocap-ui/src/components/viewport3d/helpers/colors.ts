import { Color } from "three";

export const COLORS = {
    // Keypoints - raw are dimmer/smaller, filtered are brighter/larger
    raw:            new Color("#CCC"),
    filtered:       new Color("#44FF88"),
    // Rigid bodies
    rigidBody:      new Color("#CC8833"),
    rigidBodyX:     new Color("#FF4444"),
    rigidBodyY:     new Color("#44CC44"),
    // Face
    face:           new Color("#FFD700"),
    // Utility
    hidden:         new Color("#000000"),
} as const;
