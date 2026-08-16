// SchemaRegistry.ts
//
// Holds the active StreamSchema and resolves decoded sample blocks into typed
// frames (PointsFrame / DerivedPointsFrame / RotationsFrame / OverlayFrame) by
// cross-indexing each block's `kind` against the schema's ordered channel
// groups. The sample carries no names — the schema does.

import {
  ChannelKind,
  DtypeCode,
  OverlayLayer,
  type ChannelGroup,
  type DecodedSample,
  type DerivedPointsFrame,
  type OverlayFrame,
  type PointsFrame,
  type ResolvedSample,
  type StreamSchema,
  type TypedArrayBlock,
} from "./wire-types";

/** Narrow a decoded block to its Float32Array data, failing loud if it is not
 *  float32. Every kind resolved into a typed frame here is float32 by schema;
 *  the uint8 IMAGE_JPEG block is consumed on the image path, not here. */
function asFloat32(block: TypedArrayBlock): Float32Array {
  if (block.dtypeCode !== DtypeCode.FLOAT32 || !(block.data instanceof Float32Array)) {
    throw new Error(
      `SchemaRegistry: expected a float32 block for kind ${block.kind}, got dtype_code ${block.dtypeCode}`,
    );
  }
  return block.data;
}

export interface SchemaRegistry {
  readonly schema: StreamSchema | null;
  register(schema: StreamSchema): void;
  groupForKind(kind: ChannelKind): ChannelGroup | null;
  resolve(sample: DecodedSample): ResolvedSample;
}

function resolvePoints(names: readonly string[], cols: number, data: Float32Array): PointsFrame | null {
  // 3-column groups (x,y,z) → interleaved directly. KEYPOINTS_3D is 4-column
  // (x,y,z,reprojection_error) and is stripped to xyz here (the 4th column is
  // carried through but the renderer consumes xyz).
  if (cols === 3) return { names, data };
  if (data.length === 0) return null;
  const out = new Float32Array(names.length * 3);
  for (let i = 0; i < names.length; i++) {
    out[i * 3] = data[i * cols];
    out[i * 3 + 1] = data[i * cols + 1];
    out[i * 3 + 2] = data[i * cols + 2];
  }
  return { names, data: out };
}

function resolveQuat(names: readonly string[], cols: number, data: Float32Array): PointsFrame | null {
  if (cols !== 4) throw new Error(`SchemaRegistry: rotation block has cols=${cols}, expected 4 (wxyz)`);
  return { names, data };
}

export function createSchemaRegistry(): SchemaRegistry {
  let active: StreamSchema | null = null;

  return {
    get schema() {
      return active;
    },

    register(schema: StreamSchema): void {
      active = schema;
    },

    groupForKind(kind: ChannelKind): ChannelGroup | null {
      return active?.channels.find((g) => g.kind === kind) ?? null;
    },

    resolve(sample: DecodedSample): ResolvedSample {
      if (!active) {
        throw new Error("SchemaRegistry: no schema registered — cannot resolve sample blocks");
      }
      const schema = active; // narrow away the mutable closure for TS inside callbacks

      const pointGroup = (kind: ChannelKind) => {
        const block = sample.blocks.find((b) => b.kind === kind) ?? null;
        const group = schema.channels.find((g) => g.kind === kind) ?? null;
        return { block, group };
      };

      const kp = pointGroup(ChannelKind.KEYPOINTS_3D);
      const lm = pointGroup(ChannelKind.LANDMARKS_3D);
      const seg = pointGroup(ChannelKind.SEGMENT_ORIGINS);
      const rw = pointGroup(ChannelKind.ROTATIONS_WORLD);
      const rl = pointGroup(ChannelKind.ROTATIONS_LOCAL);
      const lengths = pointGroup(ChannelKind.SEGMENT_LENGTHS);
      const derived = pointGroup(ChannelKind.DERIVED_POINTS);

      const keypoints = kp.block && kp.group
        ? resolvePoints(kp.group.names, kp.block.cols, asFloat32(kp.block))
        : null;
      const landmarks = lm.block && lm.group
        ? resolvePoints(lm.group.names, lm.block.cols, asFloat32(lm.block))
        : null;
      const segmentOrigins = seg.block && seg.group
        ? resolvePoints(seg.group.names, seg.block.cols, asFloat32(seg.block))
        : null;
      const rotationsWorld = rw.block && rw.group
        ? resolveQuat(rw.group.names, rw.block.cols, asFloat32(rw.block))
        : null;
      const rotationsLocal = rl.block && rl.group
        ? resolveQuat(rl.group.names, rl.block.cols, asFloat32(rl.block))
        : null;

      // SEGMENT_LENGTHS: one length_mm column per segment name.
      const segmentLengths = lengths.block && lengths.group
        ? { names: lengths.group.names, data: asFloat32(lengths.block) }
        : null;

      // DERIVED_POINTS: row 0 = center_of_mass, row 1 = xcom (columns x,y,z).
      let centerOfMass: [number, number, number] | null = null;
      let xcom: [number, number, number] | null = null;
      if (derived.block && derived.group) {
        const names = derived.group.names;
        const rowOf = (name: string): [number, number, number] | null => {
          const idx = names.indexOf(name);
          if (idx === -1) return null;
          const c = derived.block!.cols;
          const v = derived.block!.data;
          const x = v[idx * c];
          if (Number.isNaN(x)) return null;
          return [v[idx * c], v[idx * c + 1], v[idx * c + 2]];
        };
        centerOfMass = rowOf("center_of_mass");
        xcom = rowOf("xcom");
      }

      const overlays: OverlayFrame[] = [];
      const overlayGroup = schema.channels.find((g) => g.kind === ChannelKind.OVERLAY_2D) ?? null;
      const reprojGroup = schema.channels.find((g) => g.kind === ChannelKind.OVERLAY_REPROJECTIONS) ?? null;
      for (const block of sample.blocks) {
        if (block.kind === ChannelKind.OVERLAY_2D && overlayGroup) {
          overlays.push({
            cameraId: block.cameraId,
            layer: block.overlayLayer,
            frameNumber: sample.frameNumber,
            names: overlayGroup.names,
            data: asFloat32(block),
          });
        } else if (block.kind === ChannelKind.OVERLAY_REPROJECTIONS && reprojGroup) {
          overlays.push({
            cameraId: block.cameraId,
            layer: OverlayLayer.REPROJECTIONS,
            frameNumber: sample.frameNumber,
            names: reprojGroup.names,
            data: asFloat32(block),
          });
        }
      }

      return {
        timestamp: sample.timestamp,
        frameNumber: sample.frameNumber,
        subjectId: sample.subjectId,
        keypoints,
        landmarks,
        segmentOrigins,
        rotationsWorld,
        rotationsLocal,
        derived: { centerOfMass, xcom },
        segmentLengths,
        overlays,
      };
    },
  };
}

export { OverlayLayer };
