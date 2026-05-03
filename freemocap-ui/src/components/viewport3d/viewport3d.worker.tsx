/**
 * Web Worker entry point for the viewport3d OffscreenCanvas renderer.
 *
 * Uses R3F v9's `createRoot(OffscreenCanvas)` API directly — no
 * @react-three/offscreen wrapper. We own the message protocol, the root
 * lifecycle, and the synthetic DOM-event plumbing CameraControls needs.
 */

import "./worker-polyfill"; // must be first — stubs `window` before @react-refresh runs
import React, { useEffect, useRef } from "react";
import { createRoot, extend, type ReconcilerRoot } from "@react-three/fiber";
import * as THREE from "three";
import { Object3D } from "three";

// R3F v9's createRoot does NOT auto-register THREE intrinsics the way <Canvas> does.
// Without this, <ambientLight/>, <mesh/>, <group/>, etc. throw "not part of the
// THREE namespace" at reconcile time. Must run before any render.
extend(THREE);
import type CameraControlsImpl from "camera-controls";

import { workerDataStore } from "./WorkerDataStore";
import { WorkerDataProvider, WorkerVisibilitySync } from "./WorkerDataContext";
import { KeypointsSourceProvider } from "./KeypointsSourceContext";
import { ViewportStateProvider, useViewportState } from "./scene/ViewportStateContext";
import { ThreeJsScene } from "./ThreeJsScene";
import { fitCameraToPoints } from "./scene/SceneCamera";

console.log("[viewport3d worker] module loaded");

// Z-up world — must match the main thread setting in ThreeJsCanvas.
Object3D.DEFAULT_UP.set(0, 0, 1);

// ---------------------------------------------------------------------------
// Synthetic DOM stubs for CameraControls
//
// CameraControls (camera-controls package, used via @react-three/drei) calls a
// handful of DOM methods on the canvas element it attaches to. OffscreenCanvas
// is an EventTarget — addEventListener works — but it lacks
// getBoundingClientRect / setPointerCapture / style / ownerDocument. We
// monkey-patch them so the worker-side canvas behaves like a regular element.
// ---------------------------------------------------------------------------

let canvasSize = { width: 1, height: 1, top: 0, left: 0 };

function enhanceOffscreenCanvas(canvas: OffscreenCanvas) {
    const c = canvas as unknown as Record<string, unknown>;
    c.getBoundingClientRect = () => ({
        x: 0,
        y: 0,
        left: 0,
        top: 0,
        right: canvasSize.width,
        bottom: canvasSize.height,
        width: canvasSize.width,
        height: canvasSize.height,
        toJSON: () => ({}),
    });
    c.setPointerCapture = () => {};
    c.releasePointerCapture = () => {};
    c.hasPointerCapture = () => false;
    c.focus = () => {};
    c.blur = () => {};
    c.setAttribute = () => {};
    c.removeAttribute = () => {};
    c.getAttribute = () => null;
    c.hasAttribute = () => false;
    c.contains = () => false;
    c.parentElement = null;
    c.style = new Proxy(
        { touchAction: "none", cursor: "" },
        { set: () => true, get: (t, k) => (t as Record<string, string>)[k as string] ?? "" },
    );
    c.clientWidth = canvasSize.width;
    c.clientHeight = canvasSize.height;
    // CameraControls attaches pointermove/up to ownerDocument after pointerdown
    // so drags survive leaving the canvas. We capture pointer on the main thread,
    // so all those events come to this canvas regardless — just delegate
    // addEventListener/removeEventListener through to the canvas itself.
    c.ownerDocument = {
        defaultView: globalThis,
        addEventListener: (t: string, l: EventListener, opts?: AddEventListenerOptions) =>
            canvas.addEventListener(t, l, opts),
        removeEventListener: (t: string, l: EventListener, opts?: EventListenerOptions) =>
            canvas.removeEventListener(t, l, opts),
        dispatchEvent: (e: Event) => canvas.dispatchEvent(e),
    };
    Object.defineProperty(c, "clientWidth", { get: () => canvasSize.width });
    Object.defineProperty(c, "clientHeight", { get: () => canvasSize.height });
}

// Synthetic event class — workers may not expose PointerEvent in all engines,
// and even where they do, constructing one cross-realm from postMessage data is
// fiddly. A plain Event subclass with the fields copied on satisfies every
// access pattern CameraControls and r3f's event manager use.
class SyntheticDomEvent extends Event {
    constructor(type: string, init: Record<string, unknown>) {
        super(type, { bubbles: true, cancelable: true });
        Object.assign(this, init);
    }
}

// ---------------------------------------------------------------------------
// Root lifecycle
// ---------------------------------------------------------------------------

let root: ReconcilerRoot<OffscreenCanvas> | null = null;
let canvas: OffscreenCanvas | null = null;

async function initRoot(
    offscreen: OffscreenCanvas,
    width: number,
    height: number,
    pixelRatio: number,
) {
    canvas = offscreen;
    canvasSize = { width, height, top: 0, left: 0 };
    enhanceOffscreenCanvas(offscreen);

    root = createRoot<OffscreenCanvas>(offscreen);
    await root.configure({
        size: { width, height, top: 0, left: 0 },
        dpr: pixelRatio,
        camera: { position: [1500, 1500, 1500], fov: 75, near: 0.1, far: 100000 },
        gl: { antialias: false, logarithmicDepthBuffer: false },
        frameloop: "demand",
        // No event manager — pointer events are dispatched directly to the
        // canvas EventTarget, where CameraControls listens via addEventListener.
        events: undefined,
    });
    root.render(<WorkerScene />);
    console.log("[viewport3d worker] root created and rendering");
}

async function resizeRoot(width: number, height: number, top: number, left: number) {
    if (!root) return;
    canvasSize = { width, height, top, left };
    await root.configure({ size: { width, height, top, left } });
}

// ---------------------------------------------------------------------------
// Message router (single handler — no dual-listener kludge)
// ---------------------------------------------------------------------------

self.addEventListener("message", (event: MessageEvent) => {
    const msg = event.data as { type?: string; data?: unknown; payload?: unknown };
    const type = msg?.type;
    if (!type) return;

    switch (type) {
        case "init": {
            const p = msg.payload as {
                canvas: OffscreenCanvas;
                width: number;
                height: number;
                pixelRatio: number;
            };
            initRoot(p.canvas, p.width, p.height, p.pixelRatio);
            break;
        }
        case "resize": {
            const p = msg.payload as { width: number; height: number; top: number; left: number };
            resizeRoot(p.width, p.height, p.top, p.left);
            break;
        }
        case "domEvent": {
            const p = msg.payload as { eventType: string; init: Record<string, unknown> };
            if (canvas) {
                canvas.dispatchEvent(new SyntheticDomEvent(p.eventType, p.init));
            }
            break;
        }
        default:
            // App data → store
            workerDataStore.dispatch(type, msg.data);
    }
});

// ---------------------------------------------------------------------------
// Stats forwarder
// ---------------------------------------------------------------------------

function WorkerStatsForwarder() {
    const { statsRef } = useViewportState();
    useEffect(() => {
        const id = setInterval(() => {
            (self as unknown as Worker).postMessage({
                type: "stats",
                data: { ...statsRef.current },
            });
        }, 500);
        return () => clearInterval(id);
    }, [statsRef]);
    return null;
}

// ---------------------------------------------------------------------------
// Root scene component
// ---------------------------------------------------------------------------

function WorkerScene() {
    const controlsRef = useRef<CameraControlsImpl>(null!);

    useEffect(() => {
        console.log("[viewport3d worker] WorkerScene mounted");
        const unsub1 = workerDataStore.subscribeToFitCamera((pts) => {
            fitCameraToPoints(controlsRef.current, pts);
        });
        const unsub2 = workerDataStore.subscribeToResetCamera(() => {
            controlsRef.current?.reset(true);
        });
        return () => {
            unsub1();
            unsub2();
        };
    }, []);

    return (
        <KeypointsSourceProvider source={workerDataStore}>
            <ViewportStateProvider>
                <WorkerVisibilitySync />
                <WorkerStatsForwarder />
                <WorkerDataProvider>
                    <ThreeJsScene cameraControlsRef={controlsRef} />
                </WorkerDataProvider>
            </ViewportStateProvider>
        </KeypointsSourceProvider>
    );
}
