// SchemaRegistry.ts
//
// Holds the active StreamSchema and resolves decoded sample blocks into typed
// frames (PointsFrame / DerivedPointsFrame / RotationsFrame / OverlayFrame) by
// cross-indexing each block's `kind` against the schema's ordered channel
// groups. The sample carries no names — the schema does.

import {
  ChannelKind,
  OverlayLayer,
  type ChannelGroup,
  type DecodedSample,
  type DerivedPointsFrame,
  type OverlayFrame,
  type PointsFrame,
  type ResolvedSample,
  type StreamSchema,
} from "./types";

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
      const derived = pointGroup(ChannelKind.DERIVED_POINTS);

      const keypoints = kp.block && kp.group
        ? resolvePoints(kp.group.names, kp.block.cols, kp.block.data)
        : null;
      const landmarks = lm.block && lm.group
        ? resolvePoints(lm.group.names, lm.block.cols, lm.block.data)
        : null;
      const segmentOrigins = seg.block && seg.group
        ? resolvePoints(seg.group.names, seg.block.cols, seg.block.data)
        : null;
      const rotationsWorld = rw.block && rw.group
        ? resolveQuat(rw.group.names, rw.block.cols, rw.block.data)
        : null;
      const rotationsLocal = rl.block && rl.group
        ? resolveQuat(rl.group.names, rl.block.cols, rl.block.data)
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
      for (const block of sample.blocks) {
        if (block.kind !== ChannelKind.OVERLAY_2D || !overlayGroup) continue;
        overlays.push({
          cameraId: block.cameraId,
          layer: block.overlayLayer,
          names: overlayGroup.names,
          data: block.data,
        });
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
        overlays,
      };
    },
  };
}

export { OverlayLayer };
