import {CameraConfig, CaptureMode} from './cameras-types';

/** Frame rates the camera reports at `resolution`; empty when it does not report that resolution. */
export function framerateOptionsFor(modes: CaptureMode[], resolution: CameraConfig['resolution']): number[] {
    return modes.find(mode => mode.width === resolution.width && mode.height === resolution.height)?.framerates ?? [];
}

/**
 * The resolution and frame rate to request after choosing a new resolution. A frame rate the
 * new resolution does not offer becomes the closest offered rate (the lower of two equally
 * close rates, which needs less USB bandwidth). The camera default (-1) and cameras that
 * report no modes keep their frame rate.
 */
export function withResolution(
    config: CameraConfig,
    modes: CaptureMode[],
    width: number,
    height: number,
): Pick<CameraConfig, 'resolution' | 'framerate'> {
    const resolution = {width, height};
    const offered = framerateOptionsFor(modes, resolution);
    if (config.framerate <= 0 || offered.length === 0 || offered.includes(config.framerate)) {
        return {resolution, framerate: config.framerate};
    }
    const distance = (rate: number) => Math.abs(rate - config.framerate);
    const framerate = offered.reduce((best, rate) =>
        distance(rate) < distance(best) || (distance(rate) === distance(best) && rate < best) ? rate : best);
    return {resolution, framerate};
}
