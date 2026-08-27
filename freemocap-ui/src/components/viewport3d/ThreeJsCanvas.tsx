import { useCallback, useEffect, useRef } from "react";
import { Object3D } from "three";
import {
  ViewportStateProvider,
  useViewportState,
} from "./scene/ViewportStateContext";
import { ViewportOverlay } from "./scene/ViewportOverlay";
import { ViewportInspection } from "./scene/ViewportInspection";
import {
  useKeypointsSource,
  type KeypointsFrame,
} from "./KeypointsSourceContext";
import type { ResolvedModelFrame } from "@/services/server/transport/frame-types";
import { useAppSelector } from "@/store";
import {
  selectCalibrationConfig,
  selectLoadedCalibration,
} from "@/store/slices/calibration/calibration-slice";
import { useCalibrationTomlLoader } from "./hooks/useCalibrationTomlLoader";
import { type InspectionTarget, type ViewportStats } from "./helpers/viewport3d-types";

Object3D.DEFAULT_UP.set(0, 0, 1);

/** Returns true if at least one point in the frame is finite (stride 3, NaN = missing). */
function _frameHasVisiblePoints(frame: { interleaved: Float32Array }): boolean {
  const arr = frame.interleaved;
  for (let i = 0; i < arr.length; i += 3) {
    if (isFinite(arr[i]) && isFinite(arr[i + 1]) && isFinite(arr[i + 2])) {
      return true;
    }
  }
  return false;
}

/** Every tracked model's segment origins as one point cloud, for camera framing.
 *  Null when nothing has been reconstructed yet. */
function fittableOrigins(
  models: ResolvedModelFrame[] | null,
): KeypointsFrame | null {
  if (!models || models.length === 0) return null;
  const names: string[] = [];
  let total = 0;
  for (const m of models) {
    if (!m.segmentOrigins) continue;
    names.push(...m.segmentOrigins.names);
    total += m.segmentOrigins.data.length;
  }
  if (names.length === 0) return null;
  const interleaved = new Float32Array(total);
  let offset = 0;
  for (const m of models) {
    if (!m.segmentOrigins) continue;
    interleaved.set(m.segmentOrigins.data, offset);
    offset += m.segmentOrigins.data.length;
  }
  const frame = { pointNames: names, interleaved };
  return _frameHasVisiblePoints(frame) ? frame : null;
}

console.debug("[ThreeJsCanvas] creating viewport3d worker");
export const VIEWPORT_WORKER = new Worker(
  new URL("./viewport3d.worker.tsx", import.meta.url),
  { type: "module" },
);
console.debug("[ThreeJsCanvas] viewport3d worker created", VIEWPORT_WORKER);
VIEWPORT_WORKER.addEventListener("error", (e) =>
  console.error("[ThreeJsCanvas] worker error", e),
);
VIEWPORT_WORKER.addEventListener("messageerror", (e) =>
  console.error("[ThreeJsCanvas] worker messageerror", e),
);

// Vite HMR re-evaluates this module on every edit. Without disposing, each hot
// update spawns a NEW worker (its own WebGL context + Three scene) while the old
// one keeps running forever — a worker/context leak across a dev session that
// inflates heap and the Documents/worker counts in the profiler.
if (import.meta.hot) {
  import.meta.hot.dispose(() => VIEWPORT_WORKER.terminate());
}

// Shared across mounts: a deferred teardown handle. React.StrictMode unmounts and
// immediately remounts in dev; we schedule the worker teardown on unmount and let
// the remount cancel it, so it only actually fires on genuine navigation away.
let pendingViewportTeardown: ReturnType<typeof setTimeout> | null = null;

function VisibilityForwarder() {
  const { visibility } = useViewportState();
  useEffect(() => {
    VIEWPORT_WORKER.postMessage({ type: "visibility", data: visibility });
  }, [visibility]);
  return null;
}


function InspectionReceiver() {
  const { setHovered, setPinned } = useViewportState();
  useEffect(() => {
    const handler = (
      e: MessageEvent<{ type?: string; data?: { hovered: InspectionTarget | null; pinned: InspectionTarget | null } }>,
    ) => {
      if (e.data?.type === "inspection" && e.data.data) {
        if (e.data.data.pinned) console.log("[main] received pinned:", e.data.data.pinned.kind + ":" + e.data.data.pinned.name);
        setHovered(e.data.data.hovered);
        setPinned(e.data.data.pinned);
      }
    };
    VIEWPORT_WORKER.addEventListener("message", handler);
    return () => VIEWPORT_WORKER.removeEventListener("message", handler);
  }, [setHovered, setPinned]);
  return null;
}

function WorkerStatsReceiver() {
  const { statsRef } = useViewportState();
  useEffect(() => {
    const handler = (
      e: MessageEvent<{ type?: string; data?: ViewportStats }>,
    ) => {
      if (e.data?.type === "stats" && e.data.data) {
        Object.assign(statsRef.current, e.data.data);
      }
    };
    VIEWPORT_WORKER.addEventListener("message", handler);
    return () => VIEWPORT_WORKER.removeEventListener("message", handler);
  }, [statsRef]);
  return null;
}

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

export function ThreeJsCanvas() {
  const calibrationConfig = useAppSelector(selectCalibrationConfig);
  const loadedCalibration = useAppSelector(selectLoadedCalibration);
  const {
    subscribeToKeypoints,
    subscribeToModels,
    getModels,
    subscribeToModelFrames,
    getLatestModelFrames,
  } = useKeypointsSource();
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useCalibrationTomlLoader();

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

  // Tear down the worker's Three root on unmount so its WebGL context + scene are
  // released while the viewport isn't shown. Kept in its own effect (not coupled
  // to the transfer-once init effect, which early-returns on a StrictMode remount
  // and would otherwise never register a cleanup). The teardown is deferred and
  // canceled by an immediate remount, so StrictMode's dev double-invoke doesn't
  // kill the live scene — only real navigation away triggers it. The worker also
  // disposes any prior root on the next `init`, so re-entry rebuilds cleanly.
  useEffect(() => {
    if (pendingViewportTeardown !== null) {
      clearTimeout(pendingViewportTeardown);
      pendingViewportTeardown = null;
    }
    return () => {
      pendingViewportTeardown = setTimeout(() => {
        VIEWPORT_WORKER.postMessage({ type: "teardown" });
        pendingViewportTeardown = null;
      }, 0);
    };
  }, []);

  useEffect(() => {
    return subscribeToKeypoints((frame) => {
      if (!_frameHasVisiblePoints(frame)) return;
      VIEWPORT_WORKER.postMessage({ type: "keypoints", data: frame });
    });
  }, [subscribeToKeypoints]);

  // The STATIC model definitions, forwarded only when they change. Large and unchanging
  // between `model_sequence` bumps — 61 segments + 124 landmarks + 60 connections for the
  // human alone — so posting them per frame structured-clones all of that thirty times a
  // second and eats the frame budget. This is the once-per-change hop.
  useEffect(() => {
    const existing = getModels();
    if (existing) VIEWPORT_WORKER.postMessage({ type: "models", data: existing });
    return subscribeToModels((models) => {
      VIEWPORT_WORKER.postMessage({ type: "models", data: models });
    });
  }, [getModels, subscribeToModels]);

  // The per-frame numbers for every tracked model — origins, landmarks, rotations, fitted
  // lengths, derived points. The viewport runs in a Web Worker, so a channel that is not
  // forwarded here silently does not exist over there: the bones drew at a millimetre for
  // exactly that reason when the fitted lengths were missing, and the model is dimensionless
  // so there is no size to fall back to.
  useEffect(() => {
    return subscribeToModelFrames((models) => {
      VIEWPORT_WORKER.postMessage({ type: "modelFrames", data: models });
    });
  }, [subscribeToModelFrames]);

  useEffect(() => {
    VIEWPORT_WORKER.postMessage({
      type: "calibrationConfig",
      data: calibrationConfig,
    });
  }, [calibrationConfig]);

  useEffect(() => {
    VIEWPORT_WORKER.postMessage({
      type: "calibration",
      data: loadedCalibration,
    });
  }, [loadedCalibration]);

  const handleFit = useCallback(() => {
    // Frame every RECONSTRUCTED thing — a person and a board both belong in the shot —
    // rather than the raw keypoint cloud, whose untriangulated outliers would blow the
    // bounding box open.
    const postFit = (): boolean => {
      const origins = fittableOrigins(getLatestModelFrames());
      if (!origins) return false;
      VIEWPORT_WORKER.postMessage({ type: "fitCamera", data: origins });
      return true;
    };
    if (!postFit()) return;

    // Refine over 2s — each new frame recomputes the target so the camera smoothly
    // converges as the reconstruction settles.
    const start = performance.now();
    const REFINE_DURATION_MS = 2000;
    const interval = setInterval(() => {
      if (performance.now() - start >= REFINE_DURATION_MS) {
        clearInterval(interval);
        return;
      }
      postFit();
    }, 150);
  }, [getLatestModelFrames]);

  const handleReset = useCallback(() => {
    VIEWPORT_WORKER.postMessage({ type: "resetCamera" });
  }, []);

  useEffect(() => {
    const el = containerRef.current;
    const canvas = canvasRef.current;
    if (!el || !canvas) return;
    const ro = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      if (width === 0 && height === 0) return;
      const top = el.offsetTop;
      const left = el.offsetLeft;
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

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const onPointer = (e: PointerEvent) => {
      if (e.type === "pointerdown") {
        console.log("[main] forwarding pointerdown to worker");
        try {
          canvas.setPointerCapture(e.pointerId);
        } catch {
          /* noop */
        }
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
      canvas.addEventListener(t, onPointer as EventListener, {
        passive: false,
      }),
    );
    canvas.addEventListener("wheel", onWheel as EventListener, {
      passive: false,
    });
    canvas.addEventListener("contextmenu", onContextMenu);
    return () => {
      pointerTypes.forEach((t) =>
        canvas.removeEventListener(t, onPointer as EventListener),
      );
      canvas.removeEventListener("wheel", onWheel as EventListener);
      canvas.removeEventListener("contextmenu", onContextMenu);
    };
  }, []);

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
      <InspectionReceiver />
      <div
        ref={containerRef}
        tabIndex={0}
        className="3d-viewport-container pos-rel w-full h-full"
        style={{ outline: "none" }}
      >
        <canvas
          ref={canvasRef}
          className="3d-viewport br-2 w-full h-full block"
          style={{
            touchAction: "none",
             
            background: "var(--color-bg-primary)",
          }}
      
        />
        <ViewportOverlay onFitCamera={handleFit} onResetCamera={handleReset} />
        <ViewportInspection />
      </div>
    </ViewportStateProvider>
  );
}
