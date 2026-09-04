// TransportService.ts
//
// Owns the WebSocketConnection and is the single kind-keyed dispatcher for the
// self-describing CBOR wire. One binary message decodes (cbor-x) to a validated
// Message, then routes by kind:
//   frame     → resolve channels + fan out to frame subscribers (fast) + update
//               the held model/convention/camera state (change-detected)
//   log       → LogStore (append) via log subscribers
//   framerate → FramerateStore via framerate subscribers
//   app_state → connection slice via app-state subscribers
//   progress  → pipeline slices via progress subscribers
//
// Plain TS class — no React, no Redux. The ServerContextProvider subscribes to
// these and owns the Redux dispatch + frame/image rendering. The inbound
// frameAcknowledgment (displayImageSizes) is preserved via the connection send()
// path — see ServerContextProvider.

import {
    ConnectionState,
    WebSocketConnection,
} from "@/services/server/server-helpers/websocket-connection";
import { decodeMessage } from "./cbor-codec";
import { resolveFrameChannels } from "./frame-resolution";
import type {
    AppStateMessage,
    CalibratedCamera,
    CoordinateConvention,
    FramerateMessage,
    FrameMessage,
    ModelDefinition,
    ProgressMessage,
} from "./message-contract";
import type { LogRecord } from "../server-helpers/log-store";
import type {
    OverlayFrame,
    PointsFrame,
    ResolvedModelFrame,
} from "./frame-types";

export type OverlayCallback = (frame: OverlayFrame) => void;
/** Every tracked model this frame. ONE subscription rather than four singular ones
 *  (origins / rotations / lengths / derived), because those four always describe the same
 *  model and splitting them let a consumer read one model's rotations beside another's
 *  origins. A person and a charuco board arrive here together. */
export type ModelFramesCallback = (models: ResolvedModelFrame[]) => void;
export type ImageCallback = (buf: ArrayBuffer, frameNumber: number) => void;
export type ModelsCallback = (models: ModelDefinition[]) => void;
export type ConventionCallback = (convention: CoordinateConvention) => void;
export type CamerasCallback = (cameras: CalibratedCamera[]) => void;
export type LogCallback = (record: LogRecord) => void;
export type FramerateCallback = (message: FramerateMessage) => void;
export type AppStateCallback = (message: AppStateMessage) => void;
export type ProgressCallback = (message: ProgressMessage) => void;

export interface TransportServiceOptions {
    url: string;
}

/** A cheap, stable signature of the calibration: a calibration hot-reload
 *  changes the intrinsics, extrinsics or rotation and thus the signature, so
 *  the camera slice updates without comparing full object graphs every frame.
 *
 *  `intrinsics`/`extrinsics` are null for a camera the loaded calibration does not
 *  describe, which is a normal state - this runs BEFORE `fanOut`'s fault isolation, so
 *  dereferencing them unguarded would throw straight into the message dispatch loop.
 *  `match_kind` is part of the signature so an exact -> unmatched transition (or the
 *  reverse) re-fans-out even when nothing else about the camera changed. */
function cameraSignature(cameras: CalibratedCamera[]): string {
    return cameras
        .map(
            (c) =>
                `${c.id}:${c.index}:${c.rotation ?? ""}:${c.image_size[0]}x${c.image_size[1]}:` +
                `${c.match_kind ?? ""}:${c.calibration_camera_id ?? ""}:` +
                `${JSON.stringify(c.intrinsics ?? null)}:` +
                `${c.extrinsics ? c.extrinsics.quaternion_wxyz.join(",") : ""}:` +
                `${c.extrinsics ? c.extrinsics.translation.join(",") : ""}:` +
                `${JSON.stringify(c.world_position ?? "")}:${JSON.stringify(c.world_orientation ?? "")}`,
        )
        .join("|");
}

/** Call every callback in a set, isolating faults: one throwing subscriber must
 *  neither abort the fan-out for the remaining subscribers nor escape into the
 *  message dispatch loop. */
function fanOut<T>(subscribers: Set<(value: T) => void>, value: T): void {
    for (const cb of subscribers) {
        try {
            cb(value);
        } catch (error) {
            console.error("[TransportService] subscriber threw:", error);
        }
    }
}

export class TransportService {
    private readonly connection: WebSocketConnection;

    // Latest-frame refs.
    private keypointsLatest: PointsFrame | null = null;
    private modelFramesLatest: ResolvedModelFrame[] | null = null;

    // Held model/convention/camera state (change-detected, not per-frame).
    private modelsLatest: ModelDefinition[] | null = null;
    private conventionLatest: CoordinateConvention | null = null;
    private camerasLatest: CalibratedCamera[] | null = null;
    private lastModelSequence = -1;
    private lastCameraSignature: string | null = null;

    // Frame-channel subscriber sets.
    private readonly keypointsSubscribers = new Set<(f: PointsFrame) => void>();
    private readonly modelFramesSubscribers = new Set<ModelFramesCallback>();
    private readonly overlaySubscribers = new Set<OverlayCallback>();
    private readonly imageSubscribers = new Set<ImageCallback>();

    // Static-model + kind subscriber sets.
    private readonly modelsSubscribers = new Set<ModelsCallback>();
    private readonly conventionSubscribers = new Set<ConventionCallback>();
    private readonly camerasSubscribers = new Set<CamerasCallback>();
    private readonly logSubscribers = new Set<LogCallback>();
    private readonly framerateSubscribers = new Set<FramerateCallback>();
    private readonly appStateSubscribers = new Set<AppStateCallback>();
    private readonly progressSubscribers = new Set<ProgressCallback>();

    constructor(options: TransportServiceOptions) {
        this.connection = new WebSocketConnection({ url: options.url });

        this.connection.on("message", (event: MessageEvent) => this.handleMessage(event));
    }

    // ── inbound demux ────────────────────────────────────────────────────

    private handleMessage(event: MessageEvent): void {
        const data = event.data;
        // The server only sends "pong" as text; every real message is binary CBOR,
        // delivered as ArrayBuffer because binaryType is set to 'arraybuffer'.
        if (typeof data === "string") return;
        if (data instanceof ArrayBuffer) {
            this.dispatchBytes(data);
        } else {
            console.error(
                `[TransportService] received unexpected binary payload type ${data?.constructor?.name}`,
            );
        }
    }

    private dispatchBytes(buf: ArrayBuffer): void {
        const message = decodeMessage(new Uint8Array(buf));
        if (message === null) {
            // Unknown kind / unsupported version — fail soft (inbound data).
            console.warn("[TransportService] skipped an unknown or unsupported message");
            return;
        }
        switch (message.kind) {
            case "frame":
                this.handleFrame(message);
                break;
            case "log":
                fanOut(this.logSubscribers, message.record);
                break;
            case "framerate":
                fanOut(this.framerateSubscribers, message);
                break;
            case "app_state":
                fanOut(this.appStateSubscribers, message);
                break;
            case "progress":
                fanOut(this.progressSubscribers, message);
                break;
        }
    }

    private handleFrame(frame: FrameMessage): void {
        this.updateStaticModel(frame);
        const resolved = resolveFrameChannels(frame);

        if (resolved.keypoints) {
            this.keypointsLatest = resolved.keypoints;
            fanOut(this.keypointsSubscribers, resolved.keypoints);
        }
        this.modelFramesLatest = resolved.models;
        fanOut(this.modelFramesSubscribers, resolved.models);
        for (const overlay of resolved.overlays) {
            fanOut(this.overlaySubscribers, overlay);
        }

        if (frame.image) {
            // Consumers transfer the buffer into workers via postMessage, which
            // only accepts plain ArrayBuffers - so hand them one. The codec
            // hands back owned byteOffset-0 views, so this is zero-copy except
            // in the (unexpected) sliced-view case.
            const bytes = frame.image;
            const buffer =
                bytes.byteOffset === 0 && bytes.byteLength === bytes.buffer.byteLength
                    ? (bytes.buffer as ArrayBuffer)
                    : (bytes.slice().buffer as ArrayBuffer);
            // Paired with the frame's own frame number so consumers pair it
            // with its overlays atomically.
            for (const cb of this.imageSubscribers) {
                try {
                    cb(buffer, frame.frame_number);
                } catch (error) {
                    console.error("[TransportService] subscriber threw:", error);
                }
            }
        }
    }

    private updateStaticModel(frame: FrameMessage): void {
        if (frame.model_sequence !== this.lastModelSequence) {
            this.lastModelSequence = frame.model_sequence;
            this.modelsLatest = frame.models;
            this.conventionLatest = frame.convention;
            this.camerasLatest = frame.cameras;
            this.lastCameraSignature = cameraSignature(frame.cameras);
            fanOut(this.modelsSubscribers, frame.models);
            fanOut(this.conventionSubscribers, frame.convention);
            fanOut(this.camerasSubscribers, frame.cameras);
            return;
        }
        // Cameras (calibration) can change independently of the model: only emit
        // when the signature actually changed, never every frame.
        const signature = cameraSignature(frame.cameras);
        if (signature !== this.lastCameraSignature) {
            this.lastCameraSignature = signature;
            this.camerasLatest = frame.cameras;
            fanOut(this.camerasSubscribers, frame.cameras);
        }
    }

    // ── lifecycle ────────────────────────────────────────────────────────

    connect(): void {
        this.connection.connect();
    }

    disconnect(): void {
        this.connection.disconnect();
    }

    send(data: string | object): void {
        this.connection.send(data);
    }

    updateUrl(url: string): void {
        this.connection.updateUrl(url);
    }

    getState(): ConnectionState {
        return this.connection.getState();
    }

    on(event: string, cb: (...args: any[]) => void): void {
        this.connection.on(event, cb);
    }

    off(event: string, cb: (...args: any[]) => void): void {
        this.connection.off(event, cb);
    }

    // ── frame-channel subscriptions ──────────────────────────────────────

    subscribeToKeypoints(cb: (f: PointsFrame) => void): () => void {
        this.keypointsSubscribers.add(cb);
        return () => this.keypointsSubscribers.delete(cb);
    }

    subscribeToModelFrames(cb: ModelFramesCallback): () => void {
        this.modelFramesSubscribers.add(cb);
        return () => this.modelFramesSubscribers.delete(cb);
    }

    subscribeToOverlay(cb: OverlayCallback): () => void {
        this.overlaySubscribers.add(cb);
        return () => this.overlaySubscribers.delete(cb);
    }

    subscribeToImages(cb: ImageCallback): () => void {
        this.imageSubscribers.add(cb);
        return () => this.imageSubscribers.delete(cb);
    }

    // ── static-model + kind subscriptions ────────────────────────────────

    subscribeToModels(cb: ModelsCallback): () => void {
        this.modelsSubscribers.add(cb);
        return () => this.modelsSubscribers.delete(cb);
    }

    subscribeToConvention(cb: ConventionCallback): () => void {
        this.conventionSubscribers.add(cb);
        return () => this.conventionSubscribers.delete(cb);
    }

    subscribeToCameras(cb: CamerasCallback): () => void {
        this.camerasSubscribers.add(cb);
        return () => this.camerasSubscribers.delete(cb);
    }

    subscribeToLog(cb: LogCallback): () => void {
        this.logSubscribers.add(cb);
        return () => this.logSubscribers.delete(cb);
    }

    subscribeToFramerate(cb: FramerateCallback): () => void {
        this.framerateSubscribers.add(cb);
        return () => this.framerateSubscribers.delete(cb);
    }

    subscribeToAppState(cb: AppStateCallback): () => void {
        this.appStateSubscribers.add(cb);
        return () => this.appStateSubscribers.delete(cb);
    }

    subscribeToProgress(cb: ProgressCallback): () => void {
        this.progressSubscribers.add(cb);
        return () => this.progressSubscribers.delete(cb);
    }

    // ── accessors ────────────────────────────────────────────────────────

    getLatestKeypoints(): PointsFrame | null {
        return this.keypointsLatest;
    }

    getLatestModelFrames(): ResolvedModelFrame[] | null {
        return this.modelFramesLatest;
    }

    getModels(): ModelDefinition[] | null {
        return this.modelsLatest;
    }

    getConvention(): CoordinateConvention | null {
        return this.conventionLatest;
    }

    getCameras(): CalibratedCamera[] | null {
        return this.camerasLatest;
    }

    /** Reset caches on disconnect. */
    reset(): void {
        this.keypointsLatest = null;
        this.modelFramesLatest = null;
        this.modelsLatest = null;
        this.conventionLatest = null;
        this.camerasLatest = null;
        this.lastModelSequence = -1;
        this.lastCameraSignature = null;
    }
}
