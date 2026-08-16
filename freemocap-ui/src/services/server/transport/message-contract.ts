// transport/message-contract.ts
//
// The message-model contract: one Zod discriminated union over every kind of
// self-describing message. Single source of truth for the wire's message
// shapes — the backend encodes to it (cbor2) and the frontend validates against
// it (cbor-x + Zod). Replaces the schema-then-samples wire (StreamSchema /
// ChannelGroup / sample), per current-work-plans/03-transport/message-protocol.md.
//
// Envelope (every message): kind, version, timestamp, sequence — full names,
// never abbreviated. 'kind' is the discriminator. An unknown kind or an
// unsupported version is skipped + logged (fail soft — inbound data); a malformed
// payload for a KNOWN kind at a SUPPORTED version is a defect and throws.
//
// Status: step 1 of the cutover — additive. Nothing consumes this yet; the
// committed code still runs schema-then-samples.

import { z } from "zod";
import { LogRecordSchema } from "../server-helpers/log-store";

// ── Envelope ────────────────────────────────────────────────────────────
export const ENVELOPE = {
  version: z.number().int().nonnegative(),
  timestamp: z.number().finite(),
  sequence: z.number().int().nonnegative(),
} as const;

// ── Frame: the per-frame kind ───────────────────────────────────────────
// One channel is a named column block: kind + names + columns + data (a byte
// string of packed float32 little-endian, columns by names, row-major). The
// old overlay_layer byte folds into the two distinct channel kinds
// (OVERLAY_2D = detections, OVERLAY_REPROJECTIONS = reprojections); camera_id
// is present only on those per-camera overlay channels.
export const ChannelBlockSchema = z.object({
  kind: z.string(),
  names: z.array(z.string()),
  columns: z.array(z.string()),
  data: z.instanceof(Uint8Array),
  camera_id: z.string().optional(),
});
export type ChannelBlock = z.infer<typeof ChannelBlockSchema>;

export const SubjectSchema = z.object({
  subject_id: z.number().int(),
  channels: z.array(ChannelBlockSchema),
});
export type Subject = z.infer<typeof SubjectSchema>;

export const FrameMessageSchema = z.object({
  kind: z.literal("frame"),
  ...ENVELOPE,
  frame_number: z.number().int(),
  subjects: z.array(SubjectSchema),
  // Opaque multi-camera JPEG blob (the SkellyCam frontend payload). Absent on
  // an image-less frame. Per-camera blocks are the documented future shape.
  image: z.instanceof(Uint8Array).optional(),
});

// ── Replace kinds (low-frequency, idempotent, latest-wins) ──────────────

export const ConventionMessageSchema = z.object({
  kind: z.literal("convention"),
  ...ENVELOPE,
  units: z.string(),
  handedness: z.string(),
  up_axis: z.string(),
  forward_axis: z.string(),
  rotation_frame: z.string(),
  rotation_form: z.string(),
});

export const ModelMessageSchema = z.object({
  kind: z.literal("model"),
  ...ENVELOPE,
  // Ordered segment names — the name→index authority for the bone renderer.
  segments: z.array(z.string()),
  // Per-segment rest-frame orientation (wxyz): local frame → world T-pose.
  orientations: z.record(
    z.string(),
    z.tuple([z.number(), z.number(), z.number(), z.number()]),
  ),
  // Per-segment long-axis basis name ("x" | "y" | "z").
  axes: z.record(z.string(), z.enum(["x", "y", "z"])),
  // Anthropometric default rest lengths (mm) — the bone renderer's schema-time
  // length source. Live measured lengths ride the frame's SEGMENT_LENGTHS channel.
  lengths: z.record(z.string(), z.number()),
  // Parent→child name pairs (the skeleton connections, for 2D/3D drawing).
  connections: z.array(z.tuple([z.string(), z.string()])),
  hierarchy: z.record(z.string(), z.array(z.string())),
  parents: z.record(z.string(), z.string().nullable()),
  // Rest landmark positions (mm), keyed by landmark name.
  rest_positions: z.record(
    z.string(),
    z.tuple([z.number(), z.number(), z.number()]),
  ),
});

export const CameraLayoutMessageSchema = z.object({
  kind: z.literal("camera_layout"),
  ...ENVELOPE,
  camera_ids: z.array(z.string()),
  // capture-resolution [width, height] px per camera — the overlay coordinate space.
  image_sizes: z.record(z.string(), z.tuple([z.number().int(), z.number().int()])),
});

// ── Append / telemetry kinds ────────────────────────────────────────────

export const LogMessageSchema = z.object({
  kind: z.literal("log"),
  ...ENVELOPE,
  record: LogRecordSchema,
});

export const DetailedFramerateSchema = z.object({
  mean_frame_duration_ms: z.number(),
  mean_frames_per_second: z.number(),
  frame_duration_max: z.number(),
  frame_duration_min: z.number(),
  frame_duration_mean: z.number(),
  frame_duration_stddev: z.number(),
  frame_duration_median: z.number(),
  frame_duration_coefficient_of_variation: z.number(),
  calculation_window_size: z.number(),
  framerate_source: z.string(),
});

export const FramerateMessageSchema = z.object({
  kind: z.literal("framerate"),
  ...ENVELOPE,
  camera_group_id: z.string(),
  backend_framerate: DetailedFramerateSchema,
  frontend_framerate: DetailedFramerateSchema,
});

export const AppStateMessageSchema = z.object({
  kind: z.literal("app_state"),
  ...ENVELOPE,
  server_pid: z.number().int(),
  state: z.object({
    camera_groups: z.record(
      z.string(),
      z.object({
        id: z.string(),
        configs: z.record(z.string(), z.unknown()),
        cameras: z.record(z.string(), z.unknown()),
        alive: z.boolean(),
        recording_in_progress: z.boolean(),
        paused: z.boolean(),
      }),
    ),
    realtime_pipelines: z.array(
      z.object({
        id: z.string(),
        camera_group_id: z.string(),
        camera_ids: z.array(z.string()),
        alive: z.boolean(),
      }),
    ),
  }),
});

export const ProgressMessageSchema = z.object({
  kind: z.literal("progress"),
  ...ENVELOPE,
  pipeline_id: z.string(),
  pipeline_type: z.string(),
  phase: z.string(),
  progress_fraction: z.number().min(0).max(1),
  detail: z.string(),
  recording_name: z.string(),
  recording_path: z.string(),
  camera_id: z.string().optional(),
});

// ── The union ───────────────────────────────────────────────────────────
// 'calibration' is RESERVED (see message-protocol.md "Pre-swap audit"): today
// the frontend loads calibration over HTTP; the kind is added to this union when
// a live-push need exists. Until then a calibration message is an "unknown kind".
export const MessageSchema = z.discriminatedUnion("kind", [
  FrameMessageSchema,
  ConventionMessageSchema,
  ModelMessageSchema,
  CameraLayoutMessageSchema,
  LogMessageSchema,
  FramerateMessageSchema,
  AppStateMessageSchema,
  ProgressMessageSchema,
]);
export type Message = z.infer<typeof MessageSchema>;
export type MessageKind = Message["kind"];

export const KNOWN_KINDS = [
  "frame",
  "convention",
  "model",
  "camera_layout",
  "log",
  "framerate",
  "app_state",
  "progress",
] as const;

export const CURRENT_VERSION = 0;

/**
 * Validate a decoded CBOR value against the union.
 * Returns null for an unknown kind or an unsupported version (fail soft — the
 * caller logs once and skips). Throws for a KNOWN kind at the current version
 * with a malformed body (fail loud — that is a defect, never silently dropped).
 */
export function parseMessage(raw: unknown): Message | null {
  if (raw === null || typeof raw !== "object") return null;
  const { kind, version } = raw as { kind?: unknown; version?: unknown };
  if (typeof kind !== "string") return null;
  if (!(KNOWN_KINDS as readonly string[]).includes(kind)) return null;
  if (typeof version !== "number" || version !== CURRENT_VERSION) return null;
  return MessageSchema.parse(raw);
}
