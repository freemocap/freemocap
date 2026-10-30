import type {InspectionTarget} from "../helpers/viewport3d-types";
import type {KeypointsSource} from "../KeypointsSourceContext";
import type {ResolvedModelFrame} from "@/services/server/transport/frame-types";
import type {ModelDefinition} from "@/services/server/transport/message-contract";

/** A labeled row: plain text, or a short vector of numbers with per-component labels. */
export type DetailValue =
    | { kind: "text"; text: string }
    | { kind: "numbers"; components: readonly string[]; values: readonly number[] | null; digits: number };

export interface DetailRow {
    label: string;
    value: DetailValue;
}

const XYZ = ["x", "y", "z"] as const;
const WXYZ = ["w", "x", "y", "z"] as const;

const text = (t: string): DetailValue => ({ kind: "text", text: t });
const scalar = (v: number | null, digits: number): DetailValue => ({
    kind: "numbers",
    components: [""],
    values: v === null ? null : [v],
    digits,
});
const vec3 = (v: ArrayLike<number> | null, digits: number): DetailValue => ({
    kind: "numbers",
    components: XYZ,
    values: v === null ? null : [v[0], v[1], v[2]],
    digits,
});
const quat = (v: ArrayLike<number> | null): DetailValue => ({
    kind: "numbers",
    components: WXYZ,
    values: v === null ? null : [v[0], v[1], v[2], v[3]],
    digits: 3,
});

/** "body_height" → "Body height". */
function humanize(identifier: string): string {
    const spaced = identifier.replace(/_/g, " ");
    return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

function pointAt(data: ArrayLike<number> | undefined, index: number, stride = 3, offsets: readonly number[] = [0, 1, 2]): number[] | null {
    if (!data || index < 0) return null;
    return [data[index * stride + offsets[0]], data[index * stride + offsets[1]], data[index * stride + offsets[2]]];
}

export function computeInspectionDetails(
    target: InspectionTarget,
    source: Pick<KeypointsSource, "getLatestKeypoints">,
    models: ResolvedModelFrame[] | null,
    definitionsById: Map<string, ModelDefinition>,
): DetailRow[] {
    if (target.kind === "keypoint") {
        const frame = source.getLatestKeypoints?.();
        const index = frame ? frame.pointNames.indexOf(target.name) : -1;
        return [{ label: "Position (mm)", value: vec3(pointAt(frame?.interleaved, index), 1) }];
    }

    // A selection belongs to one model occurrence, even if another uses the same names.
    const entry = models?.find(model => model.modelId === target.modelId && model.instanceId === target.instanceId);
    const definition = definitionsById.get(target.modelId);
    const identityRows: DetailRow[] = [
        {label: "Model", value: text(target.modelId)},
        {label: "Subject instance", value: scalar(target.instanceId, 0)},
    ];
    if (target.kind === "landmark" || target.kind === "mapped keypoint") {
        const points = target.kind === "mapped keypoint" ? entry?.mappedKeypoints : entry?.landmarks;
        const index = points ? points.names.indexOf(target.name) : -1;
        const landmark = definition?.landmarks.find((l) => l.name === target.name);
        return [
            ...identityRows,
            { label: "Position (mm)", value: vec3(pointAt(points?.data, index, points?.stride, points?.coordinateOffsets), 1) },
            { label: "Rest position (model units)", value: vec3(landmark?.rest_position ?? null, 3) },
        ];
    }

    const origins = entry?.segmentOrigins ?? null;
    const rotations = entry?.rotations ?? null;
    const lengths = entry?.segmentLengths ?? null;
    const originIndex = origins ? origins.names.indexOf(target.name) : -1;
    const rotationIndex = rotations ? rotations.boneNames.indexOf(target.name) : -1;
    const lengthIndex = lengths ? lengths.names.indexOf(target.name) : -1;
    const segment = definition?.segments.find((s) => s.name === target.name);
    const scaleReference = humanize(definition?.scale_reference_name ?? "scale reference");
    const fittedScaleMm = entry?.fittedScaleMm ?? null;

    // A model is dimensionless, so a length in mm always comes from the fit: the segment's
    // own fitted length where the wire carries one, otherwise its authored proportion times
    // the model's fitted scale.
    const lengthMm =
        lengthIndex >= 0 && lengths
            ? lengths.data[lengthIndex]
            : segment && fittedScaleMm !== null
              ? segment.length_proportion * fittedScaleMm
              : null;

    return [
        ...identityRows,
        { label: "Origin (mm)", value: vec3(pointAt(origins?.data, originIndex, origins?.stride, origins?.coordinateOffsets), 1) },
        { label: "Length (mm)", value: scalar(lengthMm, 1) },
        { label: `Length (× ${scaleReference.toLowerCase()})`, value: scalar(segment?.length_proportion ?? null, 3) },
        { label: `${scaleReference} (mm)`, value: fittedScaleMm !== null ? scalar(fittedScaleMm, 1) : text("not measured") },
        {
            label: "Rotation, world",
            value: quat(rotationIndex >= 0 && rotations ? rotations.worldQuaternions.slice(rotationIndex * 4, rotationIndex * 4 + 4) : null),
        },
        {
            label: "Rotation, local",
            value: quat(rotationIndex >= 0 && rotations ? rotations.localQuaternions.slice(rotationIndex * 4, rotationIndex * 4 + 4) : null),
        },
        { label: "Rest orientation", value: quat(segment?.rest_orientation ?? null) },
        {
            label: "Primary axis",
            value: !segment
                ? text("—")
                : typeof segment.primary_axis === "string"
                  ? text(segment.primary_axis)
                  : vec3(segment.primary_axis, 3),
        },
    ];
}
