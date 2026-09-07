import {RenderCommand, RenderEvent, type ScheduledRenderMessage} from './render-protocol';
// Per-camera bitmap preparation and presentation for live and scheduled images.
// Live frames use latest-frame scheduling; scheduled images remain worker-owned
// until the client explicitly presents or releases them.

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
type InboundMessage = InitMessage | FrameMessage | VisibilityMessage | ScheduledRenderMessage;
const preparedImages = new Map<number, ImageBitmap>();

self.addEventListener("message", (event: MessageEvent) => {
    const msg = event.data as InboundMessage;
    switch (msg.type) {
        case RenderCommand.Prepare:
            void prepareImage(msg);
            break;
        case RenderCommand.Present:
            try {
                const bitmap = preparedImages.get(msg.id);
                if (!bitmap) throw new Error(`Missing prepared image ${msg.id}`);
                preparedImages.delete(msg.id);
                try {drawImage(bitmap);} finally {bitmap.close();}
                workerScope.postMessage({type: RenderEvent.Presented, id: msg.id});
            } catch (error) {
                workerScope.postMessage({type: RenderEvent.Failed, id: msg.id, detail: String(error)});
            }
            break;
        case RenderCommand.Release:
            preparedImages.get(msg.id)?.close();
            preparedImages.delete(msg.id);
            break;
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
    createRawBitmap(pixelBuffer, width, height).then((rawBitmap) => {
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

    drawImage(frame);

    // If another frame arrived while rendering, keep going.
    if (pendingFrame) scheduleRender();
}

async function prepareImage(message: Extract<ScheduledRenderMessage, {type: RenderCommand.Prepare}>): Promise<void> {
    try {
        const bitmap = await createRawBitmap(message.pixelBuffer, message.width, message.height);
        preparedImages.set(message.id, bitmap);
        workerScope.postMessage({type: RenderEvent.Prepared, id: message.id});
    } catch (error) {
        workerScope.postMessage({type: RenderEvent.Failed, id: message.id, detail: String(error)});
    }
}

function drawImage(frame: ImageBitmap): void {
    if (!ctx || !offscreenCanvas) throw new Error('Camera canvas is not initialized');
    if (offscreenCanvas.width !== frame.width) offscreenCanvas.width = frame.width;
    if (offscreenCanvas.height !== frame.height) offscreenCanvas.height = frame.height;
    ctx.transferFromImageBitmap(frame);
}

function createRawBitmap(pixelBuffer: ArrayBuffer, width: number, height: number): Promise<ImageBitmap> {
    return createImageBitmap(new ImageData(new Uint8ClampedArray(pixelBuffer), width, height));
}
