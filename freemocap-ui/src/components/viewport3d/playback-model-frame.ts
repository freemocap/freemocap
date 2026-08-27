// playback-model-frame.ts
//
// Adapts a recording's tracker schema + trajectory into the SAME shape the live stream
// produces, so playback and streaming feed one set of renderers instead of two.
//
// A recording carries tracked points and name-pair edges between them — no segments, no
// rotations, no fitted scale. That is a perfectly ordinary under-specified model: its
// landmarks are the tracked points and its edges are one landmark-connection group per
// colour. Expressing it that way is what let the schema-driven renderer be deleted.

import type { TrackedObjectDefinition } from "@/services/server/server-helpers/tracked-object-definition";
import type { ResolvedModelFrame } from "@/services/server/transport/frame-types";
import type { ModelConnectionGroup, ModelDefinition } from "@/services/server/transport/message-contract";
import { BONE_SIDE_HEX, classifyBone } from "./renderers/RigidBodyBoneInstances";
import type { KeypointsFrame } from "./KeypointsSourceContext";

export const PLAYBACK_MODEL_ID = "playback_trajectories";

/** Group a schema's edges by the side of the point they END at, one group per colour.
 *
 *  The edge represents the thing hanging off its start point, so its end point names it —
 *  the same rule the live segment edges use, which is why a hand's edges come out in the
 *  hand's colour on both paths. */
function connectionGroupsFromSchema(
    schema: TrackedObjectDefinition,
): ModelConnectionGroup[] {
    const pairsBySide = new Map<string, [string, string][]>();
    for (const [start, end] of schema.connections) {
        const side = classifyBone(end);
        const existing = pairsBySide.get(side);
        if (existing) existing.push([start, end]);
        else pairsBySide.set(side, [[start, end]]);
    }
    return [...pairsBySide].map(([side, pairs]) => ({
        name: `${side}_connections`,
        pairs,
        color: BONE_SIDE_HEX[side as keyof typeof BONE_SIDE_HEX],
    }));
}

/** The recording as a model definition. Static per recording.
 *
 *  The landmark list comes from the TRAJECTORY's point order, not the schema's: renderers
 *  index landmarks positionally, so a mismatched order draws every edge to the wrong point.
 *  The schema contributes the edges. */
export function playbackModelFromSchema(
    schema: TrackedObjectDefinition,
    trajectoryPointNames: readonly string[],
): ModelDefinition {
    return {
        model_id: PLAYBACK_MODEL_ID,
        segments: [],
        landmarks: trajectoryPointNames.map((name) => ({ name })),
        connections: [],
        landmark_groups: [],
        landmark_connections: connectionGroupsFromSchema(schema),
        scale_reference_name: "body_height",
    };
}

/** One playback frame in live-stream shape. Carries no definition — that travels on the
 *  change-detected models channel and is joined by `modelId`. */
export function playbackModelFrame(frame: KeypointsFrame): ResolvedModelFrame {
    return {
        modelId: PLAYBACK_MODEL_ID,
        fittedScaleMm: null,
        segmentOrigins: null,
        landmarks: { names: frame.pointNames, data: frame.interleaved },
        rotations: null,
        segmentLengths: null,
        derived: { centerOfMass: null, xcom: null },
    };
}
