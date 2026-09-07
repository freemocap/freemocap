import jpeg from 'jpeg-js';
import {decodeJpeg} from '../src/services/server/server-helpers/frame-processor/jpeg-decoder';
const scope = self as unknown as Worker;
self.onmessage = async (): Promise<void> => {
    const measurements: {width: number; height: number; javascriptMs: number; nativeMs: number}[] = [];
    for (const [width, height] of [[640, 360], [960, 540], [1280, 720]]) {
        const canvas = new OffscreenCanvas(width, height);
        const context = canvas.getContext('2d', {willReadFrequently: true})!;
        const pixels = context.createImageData(width, height);
        let seed = 123;
        for (let index = 0; index < pixels.data.length; index += 4) {
            seed = (1664525 * seed + 1013904223) >>> 0;
            pixels.data[index] = seed & 255;
            pixels.data[index + 1] = (seed >>> 8) & 255;
            pixels.data[index + 2] = (seed >>> 16) & 255;
            pixels.data[index + 3] = 255;
        }
        context.putImageData(pixels, 0, 0);
        const blob = await canvas.convertToBlob({type: 'image/jpeg', quality: 0.6});
        const bytes = new Uint8Array(await blob.arrayBuffer());
        const cpu = (): void => {jpeg.decode(bytes, {useTArray: true});};
        const native = async (): Promise<void> => {
            const image = await decodeJpeg(bytes);
            if (image.width !== width || image.height !== height || image.pixelBuffer.byteLength !== width * height * 4) {
                throw new Error('Decoded image shape is incorrect');
            }
        };
        cpu(); await native();
        const startCpu = performance.now();
        for (let index = 0; index < 20; index++) cpu();
        const javascriptMs = (performance.now() - startCpu) / 20;
        const startNative = performance.now();
        for (let index = 0; index < 20; index++) await native();
        measurements.push({width, height, javascriptMs, nativeMs: (performance.now() - startNative) / 20});
    }
    let invalidJpegRejected = false;
    try {await decodeJpeg(new Uint8Array([0, 1, 2]));} catch {invalidJpegRejected = true;}
    if (!invalidJpegRejected) throw new Error('Invalid JPEG was accepted');
    scope.postMessage(measurements);
};
