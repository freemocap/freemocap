import {snapshotEqual} from './snapshot-equality.js';
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
//   kinds registered by the application (options.kinds) → their own subscribers
//
// Plain TS class — no React, no Redux. The ServerContextProvider subscribes to
// these and owns the Redux dispatch + frame/image rendering. The inbound
// frameAcknowledgment (displayImageSizes) is preserved via the connection send()
// path — see ServerContextProvider.

import {
    ConnectionState,
    WebSocketConnection,
} from "./websocket-connection.js";
import { decode } from "cbor-x";
import { MessageDecoder, ownByteStrings } from "./cbor-codec.js";
import { FrameResolver } from "./frame-resolution.js";
import {resolveChannelViews, type ChannelViewsFrame} from './channel-views.js';
import {
    parseApplicationMessage,
    validateApplicationKinds,
    type ApplicationKinds,
    type ApplicationMessage,
} from "./application-kinds.js";
import type {
    AppStateMessage,
    CalibratedCamera,
    CoordinateConvention,
    FramerateMessage,
    FrameMessage,
    ModelDefinition,
    ProgressMessage,
    Message,
} from "./message-contract.js";
import type { LogRecord } from "./log-record.js";
import type {
    OverlayFrame,
    PointSourcesFrame,
    ResolvedModelFrame,
} from "./frame-types.js";

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

export interface TransportServiceOptions<Kinds extends ApplicationKinds = {}> {
    url: string;
    socketFactory?: (url: URL) => WebSocket;
    /** Message kinds defined by the application, keyed by kind. FreeMoCap's own
     *  kinds cannot be redefined. */
    kinds?: Kinds;
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

export interface DiagnosticsFrame {frameNumber: number; values: FrameMessage['diagnostics']}
export type DiagnosticsCallback = (frame: DiagnosticsFrame | null) => void;

export class TransportService<Kinds extends ApplicationKinds = {}> {
    private readonly decoder = new MessageDecoder();
    private readonly applicationKinds: Kinds;
    private readonly applicationSubscribers = new Map<string, Set<(message: unknown) => void>>();
    private readonly frameResolver = new FrameResolver();
    private diagnosticsLatest: DiagnosticsFrame | null = null;
    private diagnosticsSubscribers = new Set<DiagnosticsCallback>();

    getLatestDiagnostics(): DiagnosticsFrame | null {
        return this.diagnosticsLatest;
    }

    subscribeToDiagnostics(cb: DiagnosticsCallback): () => void {
        this.diagnosticsSubscribers.add(cb);
        return () => this.diagnosticsSubscribers.delete(cb);
    }
    private readonly connection: WebSocketConnection;
    private readonly messages = new Set<(message: Message) => void>();
    subscribeToMessages(callback: (message: Message) => void): () => void {
        this.messages.add(callback); return () => this.messages.delete(callback);
    }
    private readonly protocolErrors = new Set<(error: unknown) => void>();
    subscribeToProtocolErrors(callback: (error: unknown) => void): () => void {
        this.protocolErrors.add(callback); return () => this.protocolErrors.delete(callback);
    }

    // Latest-frame refs.
    private keypointsLatest: PointSourcesFrame | null = null;
    private modelFramesLatest: ResolvedModelFrame[] | null = null;

    // Held model/convention/camera state (change-detected, not per-frame).
    private modelsLatest: ModelDefinition[] | null = null;
    private conventionLatest: CoordinateConvention | null = null;
    private camerasLatest: CalibratedCamera[] | null = null;

    // Frame-channel subscriber sets.
    private readonly keypointsSubscribers = new Set<(f: PointSourcesFrame) => void>();
    private readonly modelFramesSubscribers = new Set<ModelFramesCallback>();
    private readonly overlaySubscribers = new Set<OverlayCallback>();
    private readonly imageSubscribers = new Set<ImageCallback>();
    private readonly channelSubscribers = new Set<(frame: ChannelViewsFrame | null) => void>();

    // Static-model + kind subscriber sets.
    private readonly modelsSubscribers = new Set<ModelsCallback>();
    private readonly conventionSubscribers = new Set<ConventionCallback>();
    private readonly camerasSubscribers = new Set<CamerasCallback>();
    private readonly logSubscribers = new Set<LogCallback>();
    private readonly framerateSubscribers = new Set<FramerateCallback>();
    private readonly appStateSubscribers = new Set<AppStateCallback>();
    private readonly progressSubscribers = new Set<ProgressCallback>();

    constructor(options: TransportServiceOptions<Kinds>) {
        const kinds = options.kinds ?? ({} as Kinds);
        validateApplicationKinds(kinds);
        // Snapshot registrations so later caller mutations cannot redefine a
        // reserved kind or change version policy on a connected stream.
        this.applicationKinds = Object.freeze(Object.fromEntries(Object.entries(kinds)
            .map(([name, definition]) => [name, Object.freeze({
                version: definition.version ?? 0, parse: definition.parse.bind(definition),
            })]))) as Kinds;
        this.connection = new WebSocketConnection({ url: options.url, socketFactory: options.socketFactory });

        this.connection.on("message", (event: MessageEvent) => {
            try { this.handleMessage(event); }
            catch (error) { fanOut(this.protocolErrors, error); }
        });
        this.connection.on("close", () => this.reset());
    }

    // ── inbound demux ────────────────────────────────────────────────────

    private handleMessage(event: MessageEvent): void {
        const data = event.data;
        // The server only sends "pong" as text; every real message is binary CBOR,
        // delivered as ArrayBuffer because binaryType is set to 'arraybuffer'.
        if (typeof data === "string") { if (data.startsWith('ping')) this.connection.sendRaw('pong'); return; }
        if (data instanceof ArrayBuffer) {
            this.dispatchBytes(data);
        } else {
            throw new TypeError(`[TransportService] received unexpected binary payload type ${data?.constructor?.name}`);
        }
    }

    private dispatchBytes(buf: ArrayBuffer): void {
        const raw = decode(new Uint8Array(buf));
        const kind = raw?.kind;
        if (typeof kind === "string" && Object.hasOwn(this.applicationKinds, kind)) {
            this.dispatchApplicationMessage(kind, raw);
            return;
        }
        const message = this.decoder.decodeValue(raw);
        if (message === null) {
            // Unknown kind / unsupported version — fail soft (inbound data).
            console.warn("[TransportService] skipped an unknown or unsupported message");
            return;
        }
        fanOut(this.messages, message);
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

    private dispatchApplicationMessage(kind: string, raw: unknown): void {
        const message = parseApplicationMessage(this.applicationKinds[kind], ownByteStrings(raw));
        if (message === null) {
            console.warn(`[TransportService] skipped an unsupported "${kind}" message version`);
            return;
        }
        const subscribers = this.applicationSubscribers.get(kind);
        if (subscribers) fanOut(subscribers, message);
    }

    private handleFrame(frame: FrameMessage): void {
        if (this.channelSubscribers.size) {
            fanOut(this.channelSubscribers, resolveChannelViews(frame));
        }
        this.diagnosticsLatest = {frameNumber: frame.frame_number, values: frame.diagnostics};
        fanOut(this.diagnosticsSubscribers, this.diagnosticsLatest);
        this.updateStaticModel(frame);
        const resolved = this.frameResolver.resolve({...frame, models: this.modelsLatest!, convention: this.conventionLatest!, cameras: this.camerasLatest!});

        this.keypointsLatest = resolved.keypoints ?? {names: [], sources: []};
        fanOut(this.keypointsSubscribers, this.keypointsLatest);
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
        if (!snapshotEqual(frame.models, this.modelsLatest)) {
            this.modelsLatest = frame.models;
            fanOut(this.modelsSubscribers, frame.models);
        }
        if (!snapshotEqual(frame.convention, this.conventionLatest)) {
            this.conventionLatest = frame.convention;
            fanOut(this.conventionSubscribers, frame.convention);
        }
        if (!snapshotEqual(frame.cameras, this.camerasLatest)) {
            this.camerasLatest = frame.cameras;
            fanOut(this.camerasSubscribers, frame.cameras);
        }
    }

    connect(): void {
        this.connection.connect();
    }

    disconnect(): void {
        this.connection.disconnect();
        this.reset();
    }

    sendDisplayFeedback(frameNumber: number, displayImageSizes?: Record<string, {width:number; height:number}>): void {
        if (!Number.isInteger(frameNumber) || frameNumber < 0) throw new TypeError('Nonnegative integer frame number required');
        if (displayImageSizes && Object.values(displayImageSizes).some(size => !Number.isFinite(size.width) || !Number.isFinite(size.height))) throw new TypeError('Finite display dimensions required');
        this.connection.send({frameNumber, displayImageSizes});
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

    /** All channels, including application kinds, from each incoming frame.
     * No replay; null marks disconnect/reset. Unused views allocate nothing. */
    subscribeToChannels(cb: (frame: ChannelViewsFrame | null) => void): () => void {
        this.channelSubscribers.add(cb);
        return () => { this.channelSubscribers.delete(cb); };
    }

    subscribeToKeypoints(cb: (f: PointSourcesFrame) => void): () => void {
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

    /** Messages of one kind registered through `options.kinds`, validated by its parser.
     *  They are not delivered to `subscribeToMessages`, which carries FreeMoCap's kinds. */
    subscribeToKind<Kind extends keyof Kinds & string>(
        kind: Kind,
        cb: (message: ApplicationMessage<Kinds[Kind]>) => void,
    ): () => void {
        if (!Object.hasOwn(this.applicationKinds, kind)) {
            throw new Error(`Message kind "${kind}" is not registered with this TransportService`);
        }
        let subscribers = this.applicationSubscribers.get(kind);
        if (!subscribers) this.applicationSubscribers.set(kind, subscribers = new Set());
        const callback = cb as (message: unknown) => void;
        subscribers.add(callback);
        return () => subscribers.delete(callback);
    }

    // ── accessors ────────────────────────────────────────────────────────

    getLatestKeypoints(): PointSourcesFrame | null {
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
        this.decoder.reset();
        this.frameResolver.reset();
        fanOut(this.channelSubscribers, null);
        this.diagnosticsLatest = null;
        fanOut(this.diagnosticsSubscribers, null);
        this.keypointsLatest = null;
        this.modelFramesLatest = null;
        this.modelsLatest = null;
        this.conventionLatest = null;
        this.camerasLatest = null;
        fanOut(this.modelsSubscribers, []);
        fanOut(this.modelFramesSubscribers, []);
        fanOut(this.keypointsSubscribers, {names: [], sources: []});
    }
}
