import {Color} from "three";

// Stick / connection colors — bright and vivid for clear body-side distinction.
export const SKELETON_COLORS = {
    left:       new Color('#4488FF'),
    right:      new Color('#FF4444'),
    center:     new Color('#00AA00'),
    leftHand:   new Color('#00FFFF'),
    rightHand:  new Color('#FF00FF'),
    face:       new Color('#FFD700'),
    hidden:     new Color('#000000'),
    charuco:    new Color('#00FF00'),
    aruco:      new Color('#FF6400'),
} as const;

// Keypoint sphere colors — muted / grey-ish so the spheres don't distract
// from the stick figure. Hand colors stay vivid per explicit request.
export const SKELETON_KEYPOINT_COLORS = {
    left:       new Color('#7788BB'),   // muted blue-grey
    right:      new Color('#BB7777'),   // muted red-grey
    center:     new Color('#888888'),   // muted grey
    leftHand:   new Color('#00FFFF'),   // cyan
    rightHand:  new Color('#FF00FF'),   // magenta
    face:       new Color('#CCAA44'),   // muted gold
    hidden:     new Color('#000000'),
    charuco:    new Color('#55AA55'),   // muted green
    aruco:      new Color('#CC5500'),   // muted orange
} as const;
