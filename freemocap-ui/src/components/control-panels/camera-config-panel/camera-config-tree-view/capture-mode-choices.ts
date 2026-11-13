import {CameraConfig, CaptureMode} from '@/store/slices/cameras/cameras-types';
import {framerateOptionsFor} from '@/store/slices/cameras/capture-modes';

type Resolution = CameraConfig['resolution'];

// Offered when a camera reports no modes.
const PRESET_RESOLUTIONS: Resolution[] = [
    {width: 640, height: 480},
    {width: 1280, height: 720},
    {width: 1920, height: 1080},
];

export const resolutionLabel = ({width, height}: Resolution): string => `${width} × ${height}`;
export const framerateLabel = (framerate: number): string => framerate > 0 ? `${framerate} fps` : 'Camera default';

export interface CaptureModeChoices {
    resolutions: Array<Resolution & {label: string}>;
    // Null when the camera reports no modes; the modal then shows no frame-rate row.
    framerates: Array<{framerate: number; label: string}> | null;
}

/** Resolution and frame-rate choices for the camera settings modal. */
export function captureModeChoices(config: CameraConfig, supportedModes: CaptureMode[]): CaptureModeChoices {
    const resolutions = supportedModes.length > 0 ? supportedModes : PRESET_RESOLUTIONS;
    return {
        resolutions: resolutions.map(({width, height}) => ({width, height, label: resolutionLabel({width, height})})),
        framerates: supportedModes.length > 0
            ? framerateOptionsFor(supportedModes, config.resolution)
                .map(framerate => ({framerate, label: framerateLabel(framerate)}))
            : null,
    };
}
