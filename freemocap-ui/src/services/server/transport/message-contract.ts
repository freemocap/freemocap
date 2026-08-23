// transport/message-contract.ts
//
// The message-model contract: one Zod discriminated union over the five message
// kinds of the self-describing CBOR wire. Single source of truth for the wire's
// message shapes — the backend encodes to it (cbor2, message_model.py) and the
// frontend validates against it (cbor-x + Zod).
//
// The frame is a fully self-describing document: it carries the coordinate
// convention, the calibrated cameras, the model definitions (segments +
// landmarks), the per-frame model instances, the tracker observations, and the
// image — all in ONE message. A single frame decodes AND renders with zero
// prior state (there is no decode-vs-render split and no held descriptor).
//
// Envelope (every message): kind, version, timestamp, sequence — full names,
// never abbreviated. 'kind' is the discriminator. An unknown kind or an
// unsupported version is skipped + logged (fail soft — inbound data); a malformed
// payload for a KNOWN kind at a SUPPORTED version is a defect and throws.

import { z } from "zod";
import { LogRecordSchema } from "../server-helpers/log-store";

// ── Envelope ────────────────────────────────────────────────────────────
export const ENVELOPE = {
  version: z.number().int().nonnegative(),
  timestamp: z.number().finite(),
  sequence: z.number().int().nonnegative(),
} as const;

// ── Frame payload primitives ────────────────────────────────────────────

/** A segment's primary axis: the axis from its origin to its distal point
 *  (where the child connects, or the tip for a leaf). A signed basis axis name,
 *  or a normalized 3-vector. */
export const PrimaryAxisSchema = z.union([
  z.enum(["x", "y", "z", "-x", "-y", "-z"]),
  z.tuple([z.number(), z.number(), z.number()]),
]);
export type PrimaryAxis = z.infer<typeof PrimaryAxisSchema>;

export const CoordinateConventionSchema = z.object({
  units: z.string(),
  handedness: z.string(),
  up_axis: z.string(),
  forward_axis: z.string(),
  rotation_frame: z.string(),
  rotation_form: z.string(),
});

export const CameraIntrinsicsSchema = z.object({
  fx: z.number(),
  fy: z.number(),
  cx: z.number(),
  cy: z.number(),
  k1: z.number(),
  k2: z.number(),
  p1: z.number(),
  p2: z.number(),
});

export const CameraExtrinsicsSchema = z.object({
  quaternion_wxyz: z.tuple([z.number(), z.number(), z.number(), z.number()]),
  translation: z.tuple([z.number(), z.number(), z.number()]),
});

export const CalibratedCameraSchema = z.object({
  id: z.string(),
  index: z.number().int(),
  rotation: z.enum(["none", "clockwise_90", "rotate_180", "counterclockwise_90"]),
  image_size: z.tuple([z.number().int(), z.number().int()]),
  intrinsics: CameraIntrinsicsSchema,
  extrinsics: CameraExtrinsicsSchema,
  world_position: z.tuple([z.number(), z.number(), z.number()]),
  world_orientation: z.array(z.tuple([z.number(), z.number(), z.number()])),
});

export const RestSegmentSchema = z.object({
  name: z.string(),
  parent: z.string().nullable(),
  primary_axis: PrimaryAxisSchema,
  rest_orientation: z.tuple([z.number(), z.number(), z.number(), z.number()]), // wxyz
  length_mm: z.number(),
  is_fully_specified: z.boolean(),
});
export type RestSegment = z.infer<typeof RestSegmentSchema>;

export const RestLandmarkSchema = z.object({
  name: z.string(),
  rest_position: z.tuple([z.number(), z.number(), z.number()]).optional(),
});
export type RestLandmark = z.infer<typeof RestLandmarkSchema>;

export const ModelDefinitionSchema = z.object({
  model_id: z.string(),
  segments: z.array(RestSegmentSchema),
  landmarks: z.array(RestLandmarkSchema),
});
export type ModelDefinition = z.infer<typeof ModelDefinitionSchema>;

/** One index-keyed column block: kind + columns + data (packed float32
 *  little-endian bytes, columns by names, row-major). Segment/landmark channels
 *  are index-keyed against the model's ordered symbol tables (names omitted);
 *  tracker-keypoint + derived channels carry their names inline. camera_id is
 *  present only on per-camera overlay channels. */
export const ChannelBlockSchema = z.object({
  kind: z.string(),
  columns: z.array(z.string()),
  data: z.instanceof(Uint8Array),
  camera_id: z.string().optional(),
  names: z.array(z.string()).optional(),
  // Full-resolution (rotated) image size of this channel's coordinate space,
  // present on per-camera overlay channels (independent of calibration).
  image_size: z.tuple([z.number().int(), z.number().int()]).optional(),
});
export type ChannelBlock = z.infer<typeof ChannelBlockSchema>;

export const ModelInstanceSchema = z.object({
  instance_id: z.number().int(),
  model_id: z.string(),
  channels: z.array(ChannelBlockSchema),
});
export type ModelInstance = z.infer<typeof ModelInstanceSchema>;

export const TrackerObservationSchema = z.object({
  tracker_id: z.string(),
  detector_type: z.string(),
  model_id: z.string(),
  channels: z.array(ChannelBlockSchema),
});
export type TrackerObservation = z.infer<typeof TrackerObservationSchema>;

// ── Frame kind ──────────────────────────────────────────────────────────

export const FrameMessageSchema = z.object({
  kind: z.literal("frame"),
  ...ENVELOPE,
  frame_number: z.number().int(),
  model_sequence: z.number().int(),
  convention: CoordinateConventionSchema,
  cameras: z.array(CalibratedCameraSchema),
  models: z.array(ModelDefinitionSchema),
  instances: z.array(ModelInstanceSchema),
  trackers: z.array(TrackerObservationSchema),
  // Opaque multi-camera JPEG blob (the SkellyCam frontend payload). Absent on
  // an image-less frame.
  image: z.instanceof(Uint8Array).optional(),
});
export type FrameMessage = z.infer<typeof FrameMessageSchema>;

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

export type CoordinateConvention = z.infer<typeof CoordinateConventionSchema>;
export type CameraIntrinsics = z.infer<typeof CameraIntrinsicsSchema>;
export type CameraExtrinsics = z.infer<typeof CameraExtrinsicsSchema>;
export type CalibratedCamera = z.infer<typeof CalibratedCameraSchema>;
export type LogMessage = z.infer<typeof LogMessageSchema>;
export type DetailedFramerate = z.infer<typeof DetailedFramerateSchema>;
export type FramerateMessage = z.infer<typeof FramerateMessageSchema>;
export type AppStateMessage = z.infer<typeof AppStateMessageSchema>;
export type ProgressMessage = z.infer<typeof ProgressMessageSchema>;

// ── The union ───────────────────────────────────────────────────────────

export const MessageSchema = z.discriminatedUnion("kind", [
  FrameMessageSchema,
  LogMessageSchema,
  FramerateMessageSchema,
  AppStateMessageSchema,
  ProgressMessageSchema,
]);
export type Message = z.infer<typeof MessageSchema>;
export type MessageKind = Message["kind"];

export const KNOWN_KINDS = [
  "frame",
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
