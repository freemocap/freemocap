// offscreen-renderer.worker.ts
//
// Per-camera module Web Worker that owns one camera's display <canvas> (via
// OffscreenCanvas) AND composites that camera's 2D skeleton overlay. Each
// camera has its own worker, so overlay compositing runs in PARALLEL across
// cameras instead of serializing in the single decode worker. The decode
// worker returns raw bitmaps; this worker draws the skeleton overlay on top
// before display.
//
// The frame and its skeleton observation arrive in ONE message — the standard
// stream carries the image and the overlay for frame N in the same sample, so
// this worker composites the frame's own overlay (no cross-stream timing, no
// staleness heuristic). The last observation is kept until a newer one
// replaces it.

import { OverlayManager } from "@/services/server/server-helpers/image-overlay/overlay-renderer-factory";
import type { SkeletonObservation } from "@/services/server/server-helpers/image-overlay/skeleton-types";

// tsconfig uses the DOM lib (no WebWorker lib); cast self for postMessage.
const workerScope = self as unknown as Worker;

let offscreenCanvas: OffscreenCanvas | null = null;
let ctx: ImageBitmapRenderingContext | null = null;

let pendingFrame: ImageBitmap | null = null;
let renderScheduled = false;

// This worker handles exactly one camera, so a single OverlayManager + a single
// latest observation is all the state it needs.
const overlayManager = new OverlayManager();
let latestSkeleton: SkeletonObservation | null = null;
let skeletonEnabled = true;

interface InitMessage { type: "init"; canvas: OffscreenCanvas; }
interface FrameMessage {
    type: "frame";
    pixelBuffer: ArrayBuffer;
    width: number;
    height: number;
    skeleton: SkeletonObservation | null;
}
interface VisibilityMessage { type: "visibility"; charuco: boolean; skeleton: boolean; }
type InboundMessage = InitMessage | FrameMessage | VisibilityMessage;

self.addEventListener("message", (event: MessageEvent) => {
    const msg = event.data as InboundMessage;
    switch (msg.type) {
        case "init":
            offscreenCanvas = msg.canvas;
            ctx = offscreenCanvas.getContext("bitmaprenderer");
            workerScope.postMessage({ type: "initialized" });
            break;
        case "frame":
            handleFrame(msg.pixelBuffer, msg.width, msg.height, msg.skeleton);
            break;
        case "visibility":
            skeletonEnabled = msg.skeleton;
            if (!skeletonEnabled) latestSkeleton = null;
            break;
    }
});

function handleFrame(
    pixelBuffer: ArrayBuffer,
    width: number,
    height: number,
    skeleton: SkeletonObservation | null,
): void {
    if (!pixelBuffer || pixelBuffer.byteLength <= 0 || width <= 0 || height <= 0) {
        return;
    }

    // The observation travels WITH its frame; a null here means "no overlay
    // this frame" — keep the last one (replaced only by a newer observation).
    if (skeleton !== null) latestSkeleton = skeleton;
    const skeletonObs = skeletonEnabled ? latestSkeleton : null;

    // Create ImageBitmap from raw pixels — this is the GPU upload step,
    // happening independently in each per-camera worker instead of batched
    // in the decode worker's Promise.all. Frame-dropping (setPending) means
    // stale pixel buffers are discarded before ever touching the GPU.
    const imageData = new ImageData(
        new Uint8ClampedArray(pixelBuffer),
        width,
        height,
    );
    createImageBitmap(imageData).then((rawBitmap) => {
        if (skeletonObs) {
            overlayManager
                .processFrame(rawBitmap, null, skeletonObs)
                .then((composite) => setPending(composite))
                .catch((err) => {
                    rawBitmap.close();
                    console.error("Overlay composite error", err);
                });
        } else {
            setPending(rawBitmap);
        }
    }).catch((err) => {
        console.error("createImageBitmap error in camera worker", err);
    });
}

function setPending(bitmap: ImageBitmap): void {
    // Frame-dropping: keep only the latest. Close any frame this supersedes.
    if (pendingFrame) pendingFrame.close();
    pendingFrame = bitmap;
    scheduleRender();
}

function scheduleRender(): void {
    if (!renderScheduled) {
        renderScheduled = true;
        requestAnimationFrame(renderLoop);
    }
}

function renderLoop(): void {
    renderScheduled = false;
    if (!pendingFrame || !ctx || !offscreenCanvas) return;

    const frame = pendingFrame;
    pendingFrame = null;

    // Match canvas size to the frame (handles rotation / resolution changes).
    if (offscreenCanvas.width !== frame.width || offscreenCanvas.height !== frame.height) {
        offscreenCanvas.width = frame.width;
        offscreenCanvas.height = frame.height;
    }

    // transferFromImageBitmap detaches (consumes) the bitmap.
    ctx.transferFromImageBitmap(frame);

    // If another frame arrived while rendering, keep going.
    if (pendingFrame) scheduleRender();
}
