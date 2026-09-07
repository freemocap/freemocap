// Shared worker JPEG decoding returns transferable RGBA buffers.
// Camera workers own bitmap preparation and presentation.

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
        const pixelBuffers = frames.map((f) => f.pixelBuffer);

        workerScope.postMessage(
            { type: "result", requestId, frameData, pixelBuffers },
            pixelBuffers,
        );
    } catch (error) {
        workerScope.postMessage({
            type: "error",
            requestId,
            message: error instanceof Error ? error.message : String(error),
        });
    }
}
