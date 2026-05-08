import { useCallback, useEffect, useRef } from "react";
import { Box } from "@mui/material";
import { Object3D } from "three";
import { ViewportStateProvider, useViewportState } from "./scene/ViewportStateContext";
import { ViewportOverlay } from "./scene/ViewportOverlay";
import { useHasKeypointsSourceProvider, useKeypointsSource } from "./KeypointsSourceContext";
import { useServer } from "@/services";
import { useAppSelector } from "@/store";
import {
    selectCalibrationConfig,
    selectLoadedCalibration,
} from "@/store/slices/calibration/calibration-slice";
import { useCalibrationTomlLoader } from "./hooks/useCalibrationTomlLoader";
import { type ViewportStats } from "./helpers/viewport3d-types";

// FreeMoCap's world is Z-up — set once before any Three.js objects are created.
Object3D.DEFAULT_UP.set(0, 0, 1);

// ---------------------------------------------------------------------------
// Worker (module-level singleton — survives React re-renders / StrictMode)
// ---------------------------------------------------------------------------

console.log("[ThreeJsCanvas] creating viewport3d worker");
export const VIEWPORT_WORKER = new Worker(
    new URL("./viewport3d.worker.tsx", import.meta.url),
    { type: "module" },
);
console.log("[ThreeJsCanvas] viewport3d worker created", VIEWPORT_WORKER);
VIEWPORT_WORKER.addEventListener("error", (e) =>
    console.error("[ThreeJsCanvas] worker error", e),
);
VIEWPORT_WORKER.addEventListener("messageerror", (e) =>
    console.error("[ThreeJsCanvas] worker messageerror", e),
);

// transferControlToOffscreen() can only be called once per HTMLCanvasElement.
// React 19 StrictMode double-mounts components in dev; it reuses the same DOM
// element across the mount→unmount→remount cycle, so a module-level flag that
// gets reset in a cleanup function will still double-transfer the same element.
//
// Instead we mark the DOM element itself via a data attribute. This survives
// StrictMode's double-mount (same element, attribute persists) but naturally
// expires on tab switches (old element destroyed, new element is clean).

// ---------------------------------------------------------------------------
// Helper components rendered inside ViewportStateProvider
// ---------------------------------------------------------------------------

/** Forwards visibility changes to the worker so the scene shows/hides layers. */
function VisibilityForwarder() {
    const { visibility } = useViewportState();
    useEffect(() => {
        VIEWPORT_WORKER.postMessage({ type: "visibility", data: visibility });
    }, [visibility]);
    return null;
}

/** Receives stats from the worker and writes them into the main-thread statsRef. */
function WorkerStatsReceiver() {
    const { statsRef } = useViewportState();
    useEffect(() => {
        const handler = (e: MessageEvent<{ type?: string; data?: ViewportStats }>) => {
            if (e.data?.type === "stats" && e.data.data) {
                Object.assign(statsRef.current, e.data.data);
            }
        };
        VIEWPORT_WORKER.addEventListener("message", handler);
        return () => VIEWPORT_WORKER.removeEventListener("message", handler);
    }, [statsRef]);
    return null;
}

// ---------------------------------------------------------------------------
// DOM-event serialization for forwarding to the worker
//
// CameraControls reads these fields off the events it receives. Stripping the
// rest avoids sending non-cloneable structures (target, view, etc.) over
// postMessage and keeps the payload small enough to forward at full input rate.
// ---------------------------------------------------------------------------

function serializePointerEvent(e: PointerEvent, rect: DOMRect) {
    return {
        eventType: e.type,
        init: {
            pointerId: e.pointerId,
            pointerType: e.pointerType,
            isPrimary: e.isPrimary,
            button: e.button,
            buttons: e.buttons,
            clientX: e.clientX - rect.left,
            clientY: e.clientY - rect.top,
            offsetX: e.offsetX,
            offsetY: e.offsetY,
            pageX: e.pageX - rect.left,
            pageY: e.pageY - rect.top,
            screenX: e.screenX,
            screenY: e.screenY,
            movementX: e.movementX,
            movementY: e.movementY,
            ctrlKey: e.ctrlKey,
            shiftKey: e.shiftKey,
            altKey: e.altKey,
            metaKey: e.metaKey,
        },
    };
}

function serializeWheelEvent(e: WheelEvent, rect: DOMRect) {
    return {
        eventType: "wheel",
        init: {
            deltaX: e.deltaX,
            deltaY: e.deltaY,
            deltaZ: e.deltaZ,
            deltaMode: e.deltaMode,
            clientX: e.clientX - rect.left,
            clientY: e.clientY - rect.top,
            ctrlKey: e.ctrlKey,
            shiftKey: e.shiftKey,
            altKey: e.altKey,
            metaKey: e.metaKey,
        },
    };
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function ThreeJsCanvas() {
    const server = useServer();
    const calibrationConfig = useAppSelector(selectCalibrationConfig);
    const loadedCalibration = useAppSelector(selectLoadedCalibration);
    const { subscribeToKeypointsRaw, subscribeToKeypointsFiltered, getLatestKeypointsRaw } =
        useKeypointsSource();
    const isPlayback = useHasKeypointsSourceProvider();
    const containerRef = useRef<HTMLDivElement>(null);
    const canvasRef = useRef<HTMLCanvasElement>(null);

    useCalibrationTomlLoader();

    // ── OffscreenCanvas transfer + worker init ────────────────────────────
    // Uses a data-attribute on the DOM element itself (not a module-level flag)
    // to prevent double-transfer. React StrictMode reuses the same canvas DOM
    // element across its mount→unmount→remount cycle, so the attribute survives
    // the cleanup/remount and correctly blocks the second transfer. On a real
    // tab switch the old element is destroyed — the new element has no attribute.
    //
    // No cleanup teardown message: on a real unmount the worker's existing root
    // may briefly become orphaned (rendering to a now-detached OffscreenCanvas),
    // but the next mount's "init" triggers initRoot() which tears down any stale
    // root before creating a new one. This avoids the StrictMode false-positive
    // where cleanup→reinit would race with the async root.configure().
    useEffect(() => {
        const canvas = canvasRef.current;
        const container = containerRef.current;
        if (!canvas || !container) return;
        if (canvas.dataset.offscreenTransferred === "true") return;
        canvas.dataset.offscreenTransferred = "true";

        const rect = container.getBoundingClientRect();
        const width = Math.max(1, Math.floor(rect.width));
        const height = Math.max(1, Math.floor(rect.height));
        const pixelRatio = Math.min(globalThis.devicePixelRatio ?? 1, 2);

        const offscreen = canvas.transferControlToOffscreen();
        VIEWPORT_WORKER.postMessage(
            {
                type: "init",
                payload: { canvas: offscreen, width, height, pixelRatio },
            },
            [offscreen],
        );
    }, []);

    // ── High-frequency streaming data ────────────────────────────────────────
    // Frames are structured-cloned across the worker boundary. The Float32Array
    // inside each KeypointsFrame is copied, not transferred, so the main thread
    // retains access for getLatestKeypointsRaw (camera fit).
    useEffect(() => {
        return subscribeToKeypointsRaw((frame) => {
            VIEWPORT_WORKER.postMessage({ type: "keypointsRaw", data: frame });
        });
    }, [subscribeToKeypointsRaw]);

    useEffect(() => {
        return subscribeToKeypointsFiltered((frame) => {
            VIEWPORT_WORKER.postMessage({ type: "keypointsFiltered", data: frame });
        });
    }, [subscribeToKeypointsFiltered]);

    // ── Low-frequency config data ─────────────────────────────────────────────
    // During playback, FileKeypointsSourceProvider owns the schema (fetched from
    // the recording's tracker_schema.json). Pushing the live-server schema here
    // would overwrite it with rtmpose_wholebody, breaking hand/face connections.
    useEffect(() => {
        if (isPlayback) return;
        VIEWPORT_WORKER.postMessage({
            type: "schemaState",
            data: {
                activeTrackerId: server.activeTrackerId,
                trackerSchemas: server.trackerSchemas,
            },
        });
    }, [isPlayback, server.activeTrackerId, server.trackerSchemas]);

    useEffect(() => {
        VIEWPORT_WORKER.postMessage({ type: "calibrationConfig", data: calibrationConfig });
    }, [calibrationConfig]);

    useEffect(() => {
        VIEWPORT_WORKER.postMessage({ type: "calibration", data: loadedCalibration });
    }, [loadedCalibration]);

    // ── Camera commands ───────────────────────────────────────────────────────
    const handleFit = useCallback(() => {
        VIEWPORT_WORKER.postMessage({ type: "fitCamera", data: getLatestKeypointsRaw() });
    }, [getLatestKeypointsRaw]);

    const handleReset = useCallback(() => {
        VIEWPORT_WORKER.postMessage({ type: "resetCamera" });
    }, []);

    // ── Resize ───────────────────────────────────────────────────────────────
    useEffect(() => {
        const el = containerRef.current;
        const canvas = canvasRef.current;
        if (!el || !canvas) return;
        const ro = new ResizeObserver((entries) => {
            const { width, height } = entries[0].contentRect;
            if (width === 0 && height === 0) return;
            // Read layout properties BEFORE writing CSS to avoid forced reflow.
            const top = el.offsetTop;
            const left = el.offsetLeft;
            // Set CSS size on the visible canvas — the OffscreenCanvas backing
            // store is sized by the worker via root.configure({size}).
            canvas.style.width = `${width}px`;
            canvas.style.height = `${height}px`;
            VIEWPORT_WORKER.postMessage({
                type: "resize",
                payload: {
                    width: Math.floor(width),
                    height: Math.floor(height),
                    top,
                    left,
                },
            });
        });
        ro.observe(el);
        return () => ro.disconnect();
    }, []);

    // ── Pointer / wheel event forwarding ─────────────────────────────────────
    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;

        const onPointer = (e: PointerEvent) => {
            // capture pointer on the visible element so move/up still fire after leaving the canvas
            if (e.type === "pointerdown") {
                try { canvas.setPointerCapture(e.pointerId); } catch { /* noop */ }
            }
            const rect = canvas.getBoundingClientRect();
            VIEWPORT_WORKER.postMessage({
                type: "domEvent",
                payload: serializePointerEvent(e, rect),
            });
        };
        const onWheel = (e: WheelEvent) => {
            e.preventDefault();
            const rect = canvas.getBoundingClientRect();
            VIEWPORT_WORKER.postMessage({
                type: "domEvent",
                payload: serializeWheelEvent(e, rect),
            });
        };
        const onContextMenu = (e: Event) => e.preventDefault();

        const pointerTypes = [
            "pointerdown",
            "pointermove",
            "pointerup",
            "pointercancel",
            "pointerleave",
        ] as const;
        pointerTypes.forEach((t) =>
            canvas.addEventListener(t, onPointer as EventListener, { passive: false }),
        );
        canvas.addEventListener("wheel", onWheel as EventListener, { passive: false });
        canvas.addEventListener("contextmenu", onContextMenu);
        return () => {
            pointerTypes.forEach((t) =>
                canvas.removeEventListener(t, onPointer as EventListener),
            );
            canvas.removeEventListener("wheel", onWheel as EventListener);
            canvas.removeEventListener("contextmenu", onContextMenu);
        };
    }, []);

    // ── "F" key shortcut ─────────────────────────────────────────────────────
    useEffect(() => {
        const el = containerRef.current;
        if (!el) return;
        const onKey = (e: KeyboardEvent) => {
            if (e.key === "f" || e.key === "F") {
                e.preventDefault();
                handleFit();
            }
        };
        el.addEventListener("keydown", onKey);
        return () => el.removeEventListener("keydown", onKey);
    }, [handleFit]);

    return (
        <ViewportStateProvider>
            <VisibilityForwarder />
            <WorkerStatsReceiver />
            <Box
                ref={containerRef}
                tabIndex={0}
                sx={{ width: "100%", height: "100%", position: "relative", outline: "none" }}
            >
                <canvas
                    ref={canvasRef}
                    style={{
                        width: "100%",
                        height: "100%",
                        display: "block",
                        touchAction: "none",
                    }}
                />
                <ViewportOverlay onFitCamera={handleFit} onResetCamera={handleReset} />
            </Box>
        </ViewportStateProvider>
    );
}
