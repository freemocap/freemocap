// images/jpeg.ts
//
// Native JPEG decoding for image payloads, in a browser page or worker
// (createImageBitmap; OffscreenCanvas for pixels). Nothing here touches those
// APIs until called, so importing the package stays safe in Node.

import type { ImagePayload, PayloadImage } from "./image-payload.js";

/** Decoded RGBA pixels whose buffer can be transferred to another worker. */
export interface RgbaImage {
    width: number;
    height: number;
    pixelBuffer: ArrayBuffer;
}

export interface PayloadBitmap extends PayloadImage {
    bitmap: ImageBitmap;
}

export interface PayloadPixels extends PayloadImage {
    pixelBuffer: ArrayBuffer;
}

/** Decode JPEG bytes into an ImageBitmap for drawing. The caller closes it. */
export function decodeJpegBitmap(bytes: Uint8Array<ArrayBuffer>): Promise<ImageBitmap> {
    return createImageBitmap(new Blob([bytes], { type: "image/jpeg" }));
}

let pixelCanvas: OffscreenCanvas | null = null;
let pixelContext: OffscreenCanvasRenderingContext2D | null = null;

/** Decode JPEG bytes into transferable RGBA pixels. */
export async function decodeJpegRgba(bytes: Uint8Array<ArrayBuffer>): Promise<RgbaImage> {
    const bitmap = await decodeJpegBitmap(bytes);
    try {
        pixelCanvas ??= new OffscreenCanvas(1, 1);
        pixelContext ??= pixelCanvas.getContext("2d", { willReadFrequently: true });
        if (!pixelContext) throw new Error("JPEG decode canvas is unavailable");
        if (pixelCanvas.width !== bitmap.width) pixelCanvas.width = bitmap.width;
        if (pixelCanvas.height !== bitmap.height) pixelCanvas.height = bitmap.height;
        // No await between drawing and reading: concurrent decodes share this surface.
        pixelContext.drawImage(bitmap, 0, 0);
        const pixels = pixelContext.getImageData(0, 0, bitmap.width, bitmap.height);
        return { width: bitmap.width, height: bitmap.height, pixelBuffer: pixels.data.buffer };
    } finally {
        bitmap.close();
    }
}

function checkSize(image: PayloadImage, decoded: { width: number; height: number }): void {
    if (decoded.width !== image.width || decoded.height !== image.height) {
        throw new Error(`JPEG dimensions disagree with the image header for ${image.cameraId}`);
    }
}

/** Decode every camera's JPEG into an ImageBitmap; the caller closes them. When any
 *  JPEG is invalid or disagrees with its header, the decoded ones are closed and the
 *  error is thrown. */
export async function decodeImageBitmaps(payload: ImagePayload): Promise<PayloadBitmap[]> {
    const settled = await Promise.allSettled(payload.images.map(image => decodeJpegBitmap(image.jpeg)));
    try {
        return payload.images.map((image, index) => {
            const result = settled[index];
            if (result.status === "rejected") throw result.reason;
            checkSize(image, result.value);
            return { ...image, bitmap: result.value };
        });
    } catch (error) {
        for (const result of settled) if (result.status === "fulfilled") result.value.close();
        throw error;
    }
}

/** Decode every camera's JPEG into transferable RGBA pixels. */
export function decodeImagePixels(payload: ImagePayload): Promise<PayloadPixels[]> {
    return Promise.all(payload.images.map(async image => {
        const decoded = await decodeJpegRgba(image.jpeg);
        checkSize(image, decoded);
        return { ...image, pixelBuffer: decoded.pixelBuffer };
    }));
}
