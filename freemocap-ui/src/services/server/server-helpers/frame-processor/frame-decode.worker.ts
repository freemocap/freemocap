// frame-decode.worker.ts
//
// Module Web Worker that parses the binary payload and decodes each camera's
// JPEG → ImageBitmap, off the main thread. It returns RAW decoded bitmaps as
// fast as possible — overlay compositing happens downstream, in parallel, in the
// per-camera canvas workers (offscreen-renderer.worker). Keeping this worker
// decode-only means the main-thread "one decode in flight" gate releases after
// decode, so it doesn't wait on compositing.

import { parseMultiFramePayload } from "./binary-frame-parser";

// tsconfig uses the DOM lib (no WebWorker lib), so `self` is typed as Window.
// Cast to Worker for the transfer-list postMessage overload (same pattern as
// viewport3d.worker.tsx).
const workerScope = self as unknown as Worker;

interface DecodeRequest {
    type: "decode";
    payload: ArrayBuffer;
    requestId: number;
}

self.addEventListener("message", (event: MessageEvent) => {
    const msg = event.data as DecodeRequest;
    if (msg.type === "decode") {
        void handleDecode(msg.payload, msg.requestId);
    }
});

async function handleDecode(payload: ArrayBuffer, requestId: number): Promise<void> {
    try {
        const frames = await parseMultiFramePayload(payload);
        if (!frames || frames.length === 0) {
            throw new Error("No valid frames found in payload");
        }

        const frameData = frames.map((f) => ({
            cameraId: f.cameraId,
            cameraIndex: f.cameraIndex,
            frameNumber: f.frameNumber,
            width: f.width,
            height: f.height,
            colorChannels: f.colorChannels,
        }));
        const bitmaps = frames.map((f) => f.bitmap);

        workerScope.postMessage({ type: "result", requestId, frameData, bitmaps }, bitmaps);
    } catch (error) {
        workerScope.postMessage({
            type: "error",
            requestId,
            message: error instanceof Error ? error.message : String(error),
        });
    }
}
