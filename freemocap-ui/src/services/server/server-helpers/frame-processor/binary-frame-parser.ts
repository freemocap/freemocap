// binary-frame-parser.ts
// @freemocap/client reads SkellyCam's image payload and decodes its JPEGs; the
// camera workers receive each camera's RGBA pixels with its identity.
import {decodeImagePixels, readImagePayload} from '@freemocap/client/images';

export interface ParsedFrame {
    cameraId: string;
    cameraIndex: number;
    frameNumber: number;
    width: number;
    height: number;
    colorChannels: number;
    pixelBuffer: ArrayBuffer;
}

/** Read a multi-camera image payload and decode every camera's JPEG to RGBA.
 *  Throws for a malformed payload or JPEG rather than returning part of it. */
export async function parseMultiFramePayload(data: ArrayBuffer): Promise<ParsedFrame[]> {
    return decodeImagePixels(readImagePayload(data));
}
