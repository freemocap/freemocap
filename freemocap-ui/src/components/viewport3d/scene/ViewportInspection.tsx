import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useKeypointsSource, useModelDefinitionsById, type KeypointsSource } from "../KeypointsSourceContext";
import { useViewportState } from "./ViewportStateContext";
import type { InspectionKind, InspectionTarget } from "../helpers/viewport3d-types";
import type { ResolvedModelFrame } from "@/services/server/transport/frame-types";
import type { ModelDefinition } from "@/services/server/transport/message-contract";

/**
 * Hover label + click-to-pin details card for the 3D viewport. The worker does the
 * raycast picking and forwards {hovered, pinned} to the main thread; this component
 * resolves the pinned name into live numbers by reading the latest frame data.
 */

const PINNED_REFRESH_MS = 100;
const COPIED_FEEDBACK_MS = 1200;

const KIND_LABEL: Record<InspectionKind, string> = {
    keypoint: "Raw keypoint",
    "mapped keypoint": "Mapped keypoint",
    landmark: "Landmark",
    segment: "Segment",
};

/** A labeled row: plain text, or a short vector of numbers with per-component labels. */
type DetailValue =
    | { kind: "text"; text: string }
    | { kind: "numbers"; components: readonly string[]; values: readonly number[] | null; digits: number };

interface DetailRow {
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

function formatNumber(v: number, digits: number): string {
    return Number.isFinite(v) ? v.toFixed(digits) : "—";
}

function valueAsText(value: DetailValue): string {
    if (value.kind === "text") return value.text;
    if (value.values === null) return "—";
    const values = value.values;
    return value.components
        .map((c, i) => (c ? `${c}=${formatNumber(values[i], value.digits)}` : formatNumber(values[i], value.digits)))
        .join(", ");
}

/** "body_height" → "Body height". */
function humanize(identifier: string): string {
    const spaced = identifier.replace(/_/g, " ");
    return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

function pointAt(data: ArrayLike<number> | undefined, index: number): number[] | null {
    if (!data || index < 0) return null;
    return [data[index * 3], data[index * 3 + 1], data[index * 3 + 2]];
}

function computeDetails(
    target: InspectionTarget,
    source: KeypointsSource,
    models: ResolvedModelFrame[] | null,
    definitionsById: Map<string, ModelDefinition>,
): DetailRow[] {
    if (target.kind === "keypoint") {
        const frame = source.getLatestKeypoints?.();
        const index = frame ? frame.pointNames.indexOf(target.name) : -1;
        return [{ label: "Position (mm)", value: vec3(pointAt(frame?.interleaved, index), 1) }];
    }

    // A frame carries several models, so the numbers are read from the one that declares the target.
    if (target.kind === "landmark" || target.kind === "mapped keypoint") {
        const entry = models?.find(
            (m) => definitionsById.get(m.modelId)?.landmarks.some((l) => l.name === target.name),
        );
        const points = target.kind === "mapped keypoint" ? entry?.mappedKeypoints : entry?.landmarks;
        const index = points ? points.names.indexOf(target.name) : -1;
        const definition = entry ? definitionsById.get(entry.modelId) : undefined;
        const landmark = definition?.landmarks.find((l) => l.name === target.name);
        return [
            { label: "Model", value: text(entry?.modelId ?? "—") },
            { label: "Position (mm)", value: vec3(pointAt(points?.data, index), 1) },
            { label: "Rest position (model units)", value: vec3(landmark?.rest_position ?? null, 3) },
        ];
    }

    const entry = models?.find(
        (m) => definitionsById.get(m.modelId)?.segments.some((s) => s.name === target.name),
    );
    const definition = entry ? definitionsById.get(entry.modelId) : undefined;
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
        { label: "Model", value: text(entry?.modelId ?? "—") },
        { label: "Origin (mm)", value: vec3(pointAt(origins?.data, originIndex), 1) },
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

function detailsAsText(target: InspectionTarget, rows: DetailRow[]): string {
    return [`${target.name} (${KIND_LABEL[target.kind]})`, ...rows.map((r) => `  ${r.label}: ${valueAsText(r.value)}`)].join("\n");
}

/** Name label that follows the cursor while it is over a point or bone. */
function HoverLabel() {
    const { hovered } = useViewportState();
    const ref = useRef<HTMLDivElement>(null);
    const pointer = useRef({ x: 0, y: 0 });

    // Positioned by writing the transform directly, so following the mouse never re-renders React.
    useEffect(() => {
        const place = (e: MouseEvent) => {
            pointer.current = { x: e.clientX, y: e.clientY };
            const el = ref.current;
            if (el) el.style.transform = `translate(${e.clientX + 14}px, ${e.clientY + 14}px)`;
        };
        window.addEventListener("mousemove", place);
        return () => window.removeEventListener("mousemove", place);
    }, []);

    useLayoutEffect(() => {
        const el = ref.current;
        if (el) el.style.transform = `translate(${pointer.current.x + 14}px, ${pointer.current.y + 14}px)`;
    }, [hovered]);

    if (!hovered) return null;
    // Portaled to <body>: the viewport root is a size container, which would otherwise
    // become the containing block for this fixed-position label.
    return createPortal(
        <div ref={ref} className="vp-hover-label" role="tooltip">
            <span className="vp-hover-kind">{KIND_LABEL[hovered.kind]}</span>
            <span className="vp-hover-name">{hovered.name}</span>
        </div>,
        document.body,
    );
}

/** Single values sit on the label's line; vectors get a line of their own. */
function isInline(value: DetailValue): boolean {
    return value.kind === "text" || value.components.length === 1;
}

function DetailValueCell({ value }: { value: DetailValue }) {
    if (value.kind === "text") return <span className="vp-detail-text">{value.text}</span>;
    if (value.values === null) return <span className="vp-detail-text is-missing">—</span>;
    const values = value.values;
    return (
        <span className="vp-detail-numbers">
            {value.components.map((component, i) => (
                <span key={i} className="vp-num">
                    {component && <span className="vp-num-axis">{component}</span>}
                    {formatNumber(values[i], value.digits)}
                </span>
            ))}
        </span>
    );
}

/** Card with the pinned item's live numbers, a copy button and a close button. */
function PinnedDetails({ onUnpin }: { onUnpin: () => void }) {
    const { pinned } = useViewportState();
    const source = useKeypointsSource();
    const definitionsById = useModelDefinitionsById();
    const [, setTick] = useState(0);
    const [copied, setCopied] = useState(false);

    // Re-resolve on a timer so a pinned card tracks the live subject without re-rendering per frame.
    useEffect(() => {
        if (!pinned) return;
        const id = setInterval(() => setTick((t) => t + 1), PINNED_REFRESH_MS);
        return () => clearInterval(id);
    }, [pinned]);

    useEffect(() => {
        if (!pinned) return;
        const onKey = (e: KeyboardEvent) => {
            if (e.key === "Escape") onUnpin();
        };
        window.addEventListener("keydown", onKey);
        return () => window.removeEventListener("keydown", onKey);
    }, [pinned, onUnpin]);

    useEffect(() => {
        if (!copied) return;
        const id = setTimeout(() => setCopied(false), COPIED_FEEDBACK_MS);
        return () => clearTimeout(id);
    }, [copied]);

    if (!pinned) return null;
    const rows = computeDetails(pinned, source, source.getLatestModelFrames(), definitionsById.current);

    const handleCopy = async () => {
        await navigator.clipboard.writeText(detailsAsText(pinned, rows));
        setCopied(true);
    };

    return (
        <section className="vp-inspect" aria-label={`${KIND_LABEL[pinned.kind]} ${pinned.name}`}>
            <header className="vp-inspect-header">
                <div className="vp-inspect-heading">
                    <span className={`vp-kind-badge is-${pinned.kind.replace(" ", "-")}`}>{KIND_LABEL[pinned.kind]}</span>
                    <span className="vp-inspect-name">{pinned.name}</span>
                </div>
                <div className="vp-inspect-actions">
                    <button type="button" className="vp-small-button" onClick={handleCopy}>
                        {copied ? "Copied" : "Copy"}
                    </button>
                    <button type="button" className="vp-small-button is-icon" aria-label="Close (Esc)" title="Close (Esc)" onClick={onUnpin}>
                        ×
                    </button>
                </div>
            </header>
            <dl className="vp-detail-list">
                {rows.map((row) => (
                    <div key={row.label} className={isInline(row.value) ? "vp-detail-row is-inline" : "vp-detail-row"}>
                        <dt>{row.label}</dt>
                        <dd>
                            <DetailValueCell value={row.value} />
                        </dd>
                    </div>
                ))}
            </dl>
        </section>
    );
}

export function ViewportInspection({ onUnpin }: { onUnpin: () => void }) {
    return (
        <>
            <HoverLabel />
            <PinnedDetails onUnpin={onUnpin} />
        </>
    );
}
