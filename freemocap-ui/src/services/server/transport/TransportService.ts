// TransportService.ts
//
// Owns the WebSocketConnection, RoutingTable, StandardStreamDecoder,
// SchemaRegistry, and per-channel RollingWindowStores. Plain TS class — no
// React. The ServerContextProvider becomes a thin consumer of this.
//
// Data flow: stream_schema JSON (routed to SchemaRegistry) then binary
// stream_samples (decoded → resolved → fan-out to rolling-window stores +
// subscriber sets). One sample carries EVERY block for its frame — pose,
// overlays, and the IMAGE_JPEG camera images — so image and overlay consumers
// see the same frame atomically. The inbound settings/frame-ack JSON the
// server still expects (frameAcknowledgment {frameNumber, displayImageSizes})
// is preserved via the connection's send() path — see ServerContextProvider.

import {
  ConnectionState,
  WebSocketConnection,
} from "@/services/server/server-helpers/websocket-connection";
import { decodeSample, decodeSchemaObject } from "./StandardStreamDecoder";
import { createRoutingTable } from "./RoutingTable";
import { createSchemaRegistry, type SchemaRegistry } from "./SchemaRegistry";
import { RollingWindowStore } from "./RollingWindowStore";
import {
  ChannelKind,
  MessageType,
  type DerivedPointsFrame,
  type OverlayFrame,
  type PointsFrame,
  type ResolvedSample,
  type RollingChannelName,
  type RotationsFrame,
  type SegmentLengthsFrame,
  type StreamSchema,
} from "./types";

export type RotationsCallback = (frame: RotationsFrame) => void;
export type OverlayCallback = (frame: OverlayFrame) => void;
export type DerivedCallback = (frame: DerivedPointsFrame) => void;
export type SegmentLengthsCallback = (frame: SegmentLengthsFrame) => void;
export type ImageCallback = (buf: ArrayBuffer, frameNumber: number) => void;

export interface TransportServiceOptions {
  url: string;
  maxWindowFrames?: number;
}

export class TransportService {
  private readonly connection: WebSocketConnection;
  private readonly routingTable = createRoutingTable();
  private readonly schemaRegistry: SchemaRegistry = createSchemaRegistry();
  private readonly maxWindowFrames: number;

  // Rolling-window stores (per channel semantic).
  readonly keypointsWindow: RollingWindowStore<PointsFrame>;
  readonly segmentOriginsWindow: RollingWindowStore<PointsFrame>;
  readonly rotationsWorldWindow: RollingWindowStore<RotationsFrame>;
  readonly derivedWindow: RollingWindowStore<DerivedPointsFrame>;
  readonly segmentLengthsWindow: RollingWindowStore<SegmentLengthsFrame>;

  // Latest-frame refs + subscriber sets.
  private keypointsLatest: PointsFrame | null = null;
  private segmentOriginsLatest: PointsFrame | null = null;
  private rotationsLatest: RotationsFrame | null = null;
  private derivedLatest: DerivedPointsFrame | null = null;
  private segmentLengthsLatest: SegmentLengthsFrame | null = null;

  private readonly keypointsSubscribers = new Set<(f: PointsFrame) => void>();
  private readonly segmentOriginsSubscribers = new Set<(f: PointsFrame) => void>();
  private readonly rotationsSubscribers = new Set<RotationsCallback>();
  private readonly derivedSubscribers = new Set<DerivedCallback>();
  private readonly segmentLengthsSubscribers = new Set<SegmentLengthsCallback>();
  private readonly overlaySubscribers = new Set<OverlayCallback>();
  private readonly imageSubscribers = new Set<ImageCallback>();
  private readonly schemaSubscribers = new Set<(s: StreamSchema) => void>();

  constructor(options: TransportServiceOptions) {
    this.maxWindowFrames = options.maxWindowFrames ?? 100;
    this.connection = new WebSocketConnection({ url: options.url });

    this.keypointsWindow = new RollingWindowStore<PointsFrame>({ maxFrames: this.maxWindowFrames });
    this.segmentOriginsWindow = new RollingWindowStore<PointsFrame>({ maxFrames: this.maxWindowFrames });
    this.rotationsWorldWindow = new RollingWindowStore<RotationsFrame>({ maxFrames: this.maxWindowFrames });
    this.derivedWindow = new RollingWindowStore<DerivedPointsFrame>({ maxFrames: this.maxWindowFrames });
    this.segmentLengthsWindow = new RollingWindowStore<SegmentLengthsFrame>({ maxFrames: this.maxWindowFrames });

    this.wireRoutes();
  }

  private wireRoutes(): void {
    this.routingTable.registerJson("stream_schema", (raw) => {
      try {
        const schema = decodeSchemaObject(raw);
        this.schemaRegistry.register(schema);
        // Fire schema subscribers so low-frequency consumers (e.g. the rigid-
        // body renderer's name→index map) rebuild once at schema time, not per frame.
        for (const cb of this.schemaSubscribers) cb(schema);
      } catch (err) {
        // Schema JSON is authoritative; a malformed schema cannot be trusted,
        // but its arrival must not be indistinguishable from "no schema yet".
        console.error("TransportService: dropped malformed stream_schema:", err);
      }
    });

    this.routingTable.registerBinary(MessageType.SAMPLE_HEADER, (buf) => {
      const schema = this.schemaRegistry.schema;
      if (!schema) return; // sample before schema — drop (schema-once contract).
      const decoded = decodeSample(buf, schema);
      const resolved = this.schemaRegistry.resolve(decoded);

      // The IMAGE_JPEG block: copy the uint8 view out of the wire buffer (the
      // buffer may be reused) and fan it to the image subscribers with the
      // sample's frame number — the image and the overlays for frame N arrive
      // in the SAME sample.
      const imageBlock = decoded.blocks.find((b) => b.kind === ChannelKind.IMAGE_JPEG);
      if (imageBlock && imageBlock.data instanceof Uint8Array) {
        const copy = new Uint8Array(imageBlock.data);
        this.imageSubscribers.forEach((cb) => cb(copy.buffer, decoded.frameNumber));
      }

      this.acceptResolved(resolved);
    });

    // Every binary frame on this connection is a standard-stream sample; there
    // is no second image protocol to fall through to.

    this.connection.on("message", (event: MessageEvent) => {
      const data = event.data;
      if (typeof data === "string") {
        if (data === "pong") return;
        let message: Record<string, any> | null = null;
        try {
          message = JSON.parse(data);
        } catch {
          return;
        }
        if (message) this.routingTable.routeJson(message);
      } else if (data instanceof ArrayBuffer) {
        this.routingTable.routeBinary(data);
      }
    });
  }

  private acceptResolved(resolved: ResolvedSample): void {
    if (resolved.keypoints) {
      this.keypointsLatest = resolved.keypoints;
      this.keypointsWindow.push(resolved.keypoints);
      this.keypointsSubscribers.forEach((cb) => cb(resolved.keypoints!));
    }
    if (resolved.segmentOrigins) {
      this.segmentOriginsLatest = resolved.segmentOrigins;
      this.segmentOriginsWindow.push(resolved.segmentOrigins);
      this.segmentOriginsSubscribers.forEach((cb) => cb(resolved.segmentOrigins!));
    }
    if (resolved.rotationsWorld || resolved.rotationsLocal) {
      const frame: RotationsFrame = {
        boneNames: resolved.rotationsWorld?.names ?? resolved.rotationsLocal?.names ?? [],
        worldQuaternions: resolved.rotationsWorld?.data ?? new Float32Array(0),
        localQuaternions: resolved.rotationsLocal?.data ?? new Float32Array(0),
      };
      this.rotationsLatest = frame;
      this.rotationsWorldWindow.push(frame);
      this.rotationsSubscribers.forEach((cb) => cb(frame));
    }
    this.derivedLatest = resolved.derived;
    this.derivedWindow.push(resolved.derived);
    this.derivedSubscribers.forEach((cb) => cb(resolved.derived));

    if (resolved.segmentLengths) {
      this.segmentLengthsLatest = resolved.segmentLengths;
      this.segmentLengthsWindow.push(resolved.segmentLengths);
      this.segmentLengthsSubscribers.forEach((cb) => cb(resolved.segmentLengths!));
    }

    for (const overlay of resolved.overlays) {
      this.overlaySubscribers.forEach((cb) => cb(overlay));
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

  // ── subscriptions ────────────────────────────────────────────────────

  subscribeToKeypoints(cb: (f: PointsFrame) => void): () => void {
    this.keypointsSubscribers.add(cb);
    return () => {
      this.keypointsSubscribers.delete(cb);
    };
  }

  subscribeToSegmentOrigins(cb: (f: PointsFrame) => void): () => void {
    this.segmentOriginsSubscribers.add(cb);
    return () => {
      this.segmentOriginsSubscribers.delete(cb);
    };
  }

  subscribeToRotations(cb: RotationsCallback): () => void {
    this.rotationsSubscribers.add(cb);
    return () => {
      this.rotationsSubscribers.delete(cb);
    };
  }

  subscribeToDerivedPoints(cb: DerivedCallback): () => void {
    this.derivedSubscribers.add(cb);
    return () => {
      this.derivedSubscribers.delete(cb);
    };
  }

  subscribeToSegmentLengths(cb: SegmentLengthsCallback): () => void {
    this.segmentLengthsSubscribers.add(cb);
    return () => {
      this.segmentLengthsSubscribers.delete(cb);
    };
  }

  subscribeToOverlay(cb: OverlayCallback): () => void {
    this.overlaySubscribers.add(cb);
    return () => {
      this.overlaySubscribers.delete(cb);
    };
  }

  /** Subscribe to stream_schema arrivals. Fires once on each (re)registration. */
  subscribeToSchema(cb: (s: StreamSchema) => void): () => void {
    this.schemaSubscribers.add(cb);
    return () => {
      this.schemaSubscribers.delete(cb);
    };
  }

  /** The most recently registered stream schema (null before first schema). */
  getSchema(): StreamSchema | null {
    return this.schemaRegistry.schema;
  }

  /** The IMAGE_JPEG block bytes for frame N — the frame number comes with the
   * sample so the consumer can pair the image with its overlay atomically. */
  subscribeToImages(cb: ImageCallback): () => void {
    this.imageSubscribers.add(cb);
    return () => {
      this.imageSubscribers.delete(cb);
    };
  }

  // ── latest-frame accessors ───────────────────────────────────────────

  getLatestKeypoints(): PointsFrame | null {
    return this.keypointsLatest;
  }

  getLatestSegmentOrigins(): PointsFrame | null {
    return this.segmentOriginsLatest;
  }

  getLatestRotations(): RotationsFrame | null {
    return this.rotationsLatest;
  }

  getLatestDerived(): DerivedPointsFrame | null {
    return this.derivedLatest;
  }

  getLatestSegmentLengths(): SegmentLengthsFrame | null {
    return this.segmentLengthsLatest;
  }

  /** Pull the rolling window for a named channel (most-recent last). */
  getRollingWindow(
    channelName: RollingChannelName,
  ): unknown[] {
    switch (channelName) {
      case "keypoints": return this.keypointsWindow.getLast();
      case "segment_origins": return this.segmentOriginsWindow.getLast();
      case "rotations_world": return this.rotationsWorldWindow.getLast();
      case "derived_points": return this.derivedWindow.getLast();
      default: {
        // Exhaustiveness check: a RollingChannelName not handled above is a bug.
        const _exhaustive: never = channelName;
        return _exhaustive;
      }
    }
  }

  /** Reset all stores and clear caches on disconnect. */
  reset(): void {
    this.keypointsWindow.clear();
    this.segmentOriginsWindow.clear();
    this.rotationsWorldWindow.clear();
    this.derivedWindow.clear();
    this.segmentLengthsWindow.clear();
    this.keypointsLatest = null;
    this.segmentOriginsLatest = null;
    this.rotationsLatest = null;
    this.derivedLatest = null;
    this.segmentLengthsLatest = null;
  }
}
