export interface DecodedImage {width: number; height: number; pixelBuffer: ArrayBuffer}

const canvas = new OffscreenCanvas(1, 1);
const context = canvas.getContext('2d', {willReadFrequently: true});

/** Native JPEG decoding with transferable RGBA output for camera rendering workers. */
export async function decodeJpeg(bytes: Uint8Array<ArrayBuffer>): Promise<DecodedImage> {
    const bitmap = await createImageBitmap(new Blob([bytes], {type: 'image/jpeg'}));
    try {
        if (!context) throw new Error('JPEG decode canvas is unavailable');
        if (canvas.width !== bitmap.width) canvas.width = bitmap.width;
        if (canvas.height !== bitmap.height) canvas.height = bitmap.height;
        // No await between drawing and reading: concurrent decodes share this surface.
        context.drawImage(bitmap, 0, 0);
        const pixels = context.getImageData(0, 0, bitmap.width, bitmap.height);
        return {width: bitmap.width, height: bitmap.height, pixelBuffer: pixels.data.buffer};
    } finally {bitmap.close();}
}
