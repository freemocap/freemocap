import {readImagePayload, decodeImagePixels} from '@freemocap/client/images';

export interface ParsedFrame {
    cameraId: string;
    cameraIndex: number;
    frameNumber: number;
    width: number;
    height: number;
    colorChannels: number;
    pixelBuffer: ArrayBuffer;
}

/** Called in the existing decode worker; returns only transferable RGBA frames. */
export async function parseMultiFramePayload(data: ArrayBuffer): Promise<ParsedFrame[] | null> {
    const images = await decodeImagePixels(readImagePayload(data));
    // Do not retain or clone the source JPEG views into camera-renderer messages.
    return images.map(({jpeg: _jpeg, ...frame}) => frame);
}
