// transport/types.ts
//
// TS mirrors of the standard-stream wire contract. The Python side is the
// authority — these MUST NOT diverge from:
//   - freemocap/core/streaming/standard_stream/stream_schema.py  (schema JSON)
//   - freemocap/core/streaming/standard_stream/stream_sample.py  (binary sample)
//   - freemocap/core/streaming/standard_stream/coordinate_convention.py
// See current-work-plans/03-transport/standard-stream-protocol.md (channels).

// ── Enums — wire values are the serialized integer ─────────────────────

export enum ChannelKind {
  KEYPOINTS_3D = 0, // tracker-named measured keypoints
  LANDMARKS_3D = 1, // the 76 hydrated standard-human landmarks
  SEGMENT_ORIGINS = 2, // segment names — transform origin (proximal joint)
  ROTATIONS_LOCAL = 3, // segment names, wxyz — parent-relative
  ROTATIONS_WORLD = 4, // segment names, wxyz — world frame
  DERIVED_POINTS = 5, // center_of_mass, xcom
  OVERLAY_2D = 6, // per camera x layer
  SEGMENT_LENGTHS = 7, // segment names, length_mm — sent every frame
  IMAGE_JPEG = 8, // camera images — one opaque multi-camera JPEG blob (uint8); split per-camera later
  OVERLAY_REPROJECTIONS = 9, // per camera — the fitted skeleton's segment-origin landmarks projected back down
}

export enum OverlayLayer {
  DETECTIONS = 0,
  REPROJECTIONS = 1,
}

// First-byte tags (MessageType in stream_sample.py). Distinct from skellycam's
// image protocol (0/1/2) and the retired legacy keypoints protocol (3/4/5).
export enum MessageType {
  SAMPLE_HEADER = 10,
  BLOCK_HEADER = 11,
  SAMPLE_FOOTER = 12,
}

// DtypeCode on the block header (stream_sample.py). float32 for point/rotation/
// scalar blocks; uint8 for the raw-bytes IMAGE_JPEG block.
export enum DtypeCode {
  FLOAT32 = 0,
  UINT8 = 1,
}

// ── Schema JSON ────────────────────────────────────────────────────────

export interface CoordinateConvention {
  units: string; // "mm" | "cm" | "m"
  handedness: string; // "right" | "left"
  up_axis: string; // "+z"
  forward_axis: string; // "+x"
  rotation_frame: string; // "local" | "world"
  rotation_form: string; // "quaternion" | "euler"
}

export interface ChannelGroup {
  kind: ChannelKind;
  names: string[];
  columns: string[];
  units: string;
}

export interface RestPose {
  positions: Record<string, [number, number, number]>;
  reference_orientations: Record<string, [number, number, number, number]>;
}

export interface StreamSchema {
  stream_id: string;
  stream_name: string;
  coordinate_convention: CoordinateConvention;
  channels: ChannelGroup[];
  connections: [string, string][];
  joint_hierarchy: Record<string, string[]>;
  segment_parents: Record<string, string | null>;
  /** Per-segment long-axis basis name (the segment's EXACT axis declaration):
   * body/hand segments declare "y", face segments declare "z". The 3D bone
   * renderer orients its unit geometry onto this axis. */
  segment_axes: Record<string, "x" | "y" | "z">;
  rest_pose: RestPose | null;
  /** Per-segment rest lengths (mm), keyed by segment name. Default-then-update:
   * anthropometric defaults on first send, then re-sent with measured values. */
  segment_lengths: Record<string, number>;
  camera_ids: string[];
  /** Per-camera capture-resolution image size [width, height] in px — the
   * coordinate space of OVERLAY_2D values. Consumers scale overlay points to
   * their own display size with it. */
  camera_image_sizes: Record<string, [number, number]>;
  max_persons: number;
  message_type: "stream_schema";
}

// ── Decoded sample ─────────────────────────────────────────────────────

/** One block of a sample, decoded to a (numElements × cols) typed array.
 *  `data` is a Float32Array for FLOAT32 blocks and a Uint8Array for UINT8
 *  (IMAGE_JPEG) blocks — discriminate with `dtypeCode`. */
export interface TypedArrayBlock {
  kind: ChannelKind;
  dtypeCode: DtypeCode;
  data: Float32Array | Uint8Array; // (numElements * cols) row-major interleaved
  numElements: number;
  cols: number;
  cameraId: string; // "" except OVERLAY_2D blocks
  overlayLayer: OverlayLayer;
}

export interface DecodedSample {
  timestamp: number;
  frameNumber: number;
  subjectId: number;
  blocks: TypedArrayBlock[];
}

// ── Resolved frames (schema-driven) ────────────────────────────────────

/** A resolved 3D keypoint/segment-origin frame: names + interleaved xyz. */
export interface PointsFrame {
  names: readonly string[];
  /** interleaved [x0,y0,z0, x1,y1,z1, …] — length names.length * 3. */
  data: Float32Array;
}

/** The per-frame SEGMENT_LENGTHS block: names + one length_mm per segment. */
export interface SegmentLengthsFrame {
  names: readonly string[];
  /** length_mm per segment — length names.length. */
  data: Float32Array;
}

export interface DerivedPointsFrame {
  centerOfMass: [number, number, number] | null;
  xcom: [number, number, number] | null;
}

export interface RotationsFrame {
  boneNames: readonly string[];
  /** interleaved wxyz — length boneNames.length * 4. */
  worldQuaternions: Float32Array;
  localQuaternions: Float32Array;
}

export interface OverlayFrame {
  cameraId: string;
  layer: OverlayLayer;
  frameNumber: number;
  names: readonly string[];
  /** interleaved [x,y,visibility, …] — length names.length * 3. */
  data: Float32Array;
}

/** Rolling-window channel keys accepted by `TransportService.getRollingWindow`. */
export type RollingChannelName =
  | "keypoints"
  | "segment_origins"
  | "rotations_world"
  | "derived_points";

// ── Resolved sample (schema-driven) ────────────────────────────────────

/** A DecodedSample resolved to typed frames by cross-indexing the schema. */
export interface ResolvedSample {
  timestamp: number;
  frameNumber: number;
  subjectId: number;
  keypoints: PointsFrame | null;
  landmarks: PointsFrame | null;
  segmentOrigins: PointsFrame | null;
  rotationsWorld: PointsFrame | null;
  rotationsLocal: PointsFrame | null;
  derived: DerivedPointsFrame;
  segmentLengths: SegmentLengthsFrame | null;
  overlays: OverlayFrame[];
}
