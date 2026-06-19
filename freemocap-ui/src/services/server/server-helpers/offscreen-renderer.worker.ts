// offscreen-renderer.worker.ts
//
// Per-camera module Web Worker that owns one camera's display <canvas> (via
// OffscreenCanvas) AND composites that camera's 2D overlay. Each camera has its
// own worker, so overlay compositing runs in PARALLEL across cameras instead of
// serializing in the single decode worker. The decode worker now returns raw
// bitmaps; this worker draws the CharUco / skeleton overlay on top before display.

import { OverlayManager } from "@/services/server/server-helpers/image-overlay/overlay-renderer-factory";
import type { CharucoObservation } from "@/services/server/server-helpers/image-overlay/charuco-types";
import type { MediapipeObservation } from "@/services/server/server-helpers/image-overlay/mediapipe-types";
import type { TrackedObjectDefinition } from "@/services/server/server-helpers/tracked-object-definition";

// tsconfig uses the DOM lib (no WebWorker lib); cast self for postMessage.
const workerScope = self as unknown as Worker;

const OVERLAY_STALE_MS = 500;

let offscreenCanvas: OffscreenCanvas | null = null;
let ctx: ImageBitmapRenderingContext | null = null;

let pendingFrame: ImageBitmap | null = null;
let renderScheduled = false;

// This worker handles exactly one camera, so a single OverlayManager + a single
// latest observation per type is all the state it needs.
const overlayManager = new OverlayManager();
let latestCharuco: CharucoObservation | null = null;
let latestMediapipe: MediapipeObservation | null = null;
let lastOverlayTime = 0;
let charucoEnabled = true;
let skeletonEnabled = true;

interface InitMessage { type: "init"; canvas: OffscreenCanvas; }
interface FrameMessage { type: "frame"; bitmap: ImageBitmap; }
interface OverlaysMessage {
    type: "overlays";
    charuco: CharucoObservation | null;
    skeleton: MediapipeObservation | null;
}
interface VisibilityMessage { type: "visibility"; charuco: boolean; skeleton: boolean; }
interface SchemaMessage {
    type: "schema";
    schemas: Record<string, TrackedObjectDefinition>;
    activeId: string | null;
}
type InboundMessage = InitMessage | FrameMessage | OverlaysMessage | VisibilityMessage | SchemaMessage;

self.addEventListener("message", (event: MessageEvent) => {
    const msg = event.data as InboundMessage;
    switch (msg.type) {
        case "init":
            offscreenCanvas = msg.canvas;
            ctx = offscreenCanvas.getContext("bitmaprenderer");
            workerScope.postMessage({ type: "initialized" });
            break;
        case "frame":
            handleFrame(msg.bitmap);
            break;
        case "overlays":
            // null means "no update this message" (not "clear") — staleness evicts.
            if (msg.charuco !== null) latestCharuco = msg.charuco;
            if (msg.skeleton !== null) latestMediapipe = msg.skeleton;
            lastOverlayTime = performance.now();
            break;
        case "visibility":
            charucoEnabled = msg.charuco;
            skeletonEnabled = msg.skeleton;
            if (!charucoEnabled) latestCharuco = null;
            if (!skeletonEnabled) latestMediapipe = null;
            break;
        case "schema":
            overlayManager.setTrackerSchemas(msg.schemas, msg.activeId ?? undefined);
            break;
    }
});

function handleFrame(rawBitmap: ImageBitmap): void {
    if (!rawBitmap || rawBitmap.width <= 0 || rawBitmap.height <= 0) {
        if (rawBitmap) rawBitmap.close();
        return;
    }

    const overlayFresh = performance.now() - lastOverlayTime <= OVERLAY_STALE_MS;
    if (!overlayFresh) {
        latestCharuco = null;
        latestMediapipe = null;
    }
    const charucoObs = charucoEnabled && overlayFresh ? latestCharuco : null;
    const mediapipeObs = skeletonEnabled && overlayFresh ? latestMediapipe : null;

    if (charucoObs || mediapipeObs) {
        // processFrame closes the raw bitmap and returns the composited one.
        // transferToImageBitmap makes this resolve synchronously, so .then()
        // callbacks for successive frames run in arrival order.
        overlayManager
            .processFrame("", rawBitmap, charucoObs, mediapipeObs)
            .then((composite) => setPending(composite))
            .catch((err) => {
                rawBitmap.close();
                console.error("Overlay composite error", err);
            });
    } else {
        setPending(rawBitmap);
    }
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
