import { useEffect, useState } from "react";
import { useKeypointsSource, type KeypointsSource } from "../KeypointsSourceContext";
import { useViewportState } from "./ViewportStateContext";
import type { InspectionTarget } from "../helpers/viewport3d-types";
import type { ModelDefinition } from "@/services/server/transport/message-contract";

/**
 * Hover tooltip + click-to-pin info panel for the 3D viewport. The worker does
 * the raycast picking and forwards {hovered, pinned} to this main-thread
 * component (via the message bridge); this component resolves the name into
 * concrete numbers by reading the live frame data.
 */

const fmt = (v: number, digits = 3) => (Number.isFinite(v) ? v.toFixed(digits) : "—");

function vec3(v: readonly [number, number, number] | number[] | Float32Array | undefined, digits = 3): string {
    if (!v || v.length < 3) return "—";
    return `(${fmt(v[0], digits)}, ${fmt(v[1], digits)}, ${fmt(v[2], digits)})`;
}

function quat(v: readonly number[] | Float32Array | undefined): string {
    if (!v || v.length < 4) return "—";
    return `w=${fmt(v[0], 4)}, x=${fmt(v[1], 4)}, y=${fmt(v[2], 4)}, z=${fmt(v[3], 4)}`;
}

interface DetailLine {
    label: string;
    value: string;
}

function findIndex(names: readonly string[] | undefined, name: string): number {
    if (!names) return -1;
    for (let i = 0; i < names.length; i++) if (names[i] === name) return i;
    return -1;
}

function computeDetails(
    target: InspectionTarget,
    source: KeypointsSource,
    models: ModelDefinition[] | null,
): DetailLine[] {
    const model = models?.[0];

    if (target.kind === "keypoint") {
        const frame = source.getLatestKeypoints?.();
        const i = findIndex(frame?.pointNames, target.name);
        const xyz = i >= 0 && frame ? [frame.interleaved[i * 3], frame.interleaved[i * 3 + 1], frame.interleaved[i * 3 + 2]] : undefined;
        return [{ label: "world", value: vec3(xyz) }];
    }

    if (target.kind === "landmark") {
        const frame = source.getLatestSkeleton?.();
        const i = findIndex(frame?.pointNames, target.name);
        const xyz = i >= 0 && frame ? [frame.interleaved[i * 3], frame.interleaved[i * 3 + 1], frame.interleaved[i * 3 + 2]] : undefined;
        const lm = model?.landmarks.find((l) => l.name === target.name);
        return [
            { label: "world", value: vec3(xyz) },
            { label: "rest (local)", value: vec3(lm?.rest_position) },
        ];
    }

    // segment
    const skeleton = source.getLatestSkeleton?.();
    const rotations = source.getLatestRotations?.();
    const lengths = source.getLatestSegmentLengths?.();
    const oi = findIndex(skeleton?.pointNames, target.name);
    const qi = findIndex(rotations?.boneNames, target.name);
    const li = findIndex(lengths?.names, target.name);
    const seg = model?.segments.find((s) => s.name === target.name);
    return [
        {
            label: "world origin",
            value: oi >= 0 && skeleton ? vec3([skeleton.interleaved[oi * 3], skeleton.interleaved[oi * 3 + 1], skeleton.interleaved[oi * 3 + 2]]) : "—",
        },
        { label: "world quaternion", value: qi >= 0 && rotations ? quat(Array.from(rotations.worldQuaternions.slice(qi * 4, qi * 4 + 4))) : "—" },
        { label: "local quaternion", value: qi >= 0 && rotations ? quat(Array.from(rotations.localQuaternions.slice(qi * 4, qi * 4 + 4))) : "—" },
        { label: "length (mm)", value: li >= 0 && lengths ? fmt(lengths.data[li]) : (seg ? fmt(seg.length_mm) : "—") },
        { label: "rest orientation", value: seg ? quat(seg.rest_orientation) : "—" },
        { label: "primary axis", value: seg ? JSON.stringify(seg.primary_axis) : "—" },
    ];
}

function detailText(target: InspectionTarget, lines: DetailLine[]): string {
    return [target.name + ` (${target.kind})`, ...lines.map((l) => `  ${l.label}: ${l.value}`)].join("\n");
}

/** Small floating label following the cursor while hovering a point/bone. */
function HoverTooltip() {
    const { hovered } = useViewportState();
    const [mouse, setMouse] = useState({ x: 0, y: 0 });

    useEffect(() => {
        const fn = (e: MouseEvent) => setMouse({ x: e.clientX, y: e.clientY });
        window.addEventListener("mousemove", fn);
        return () => window.removeEventListener("mousemove", fn);
    }, []);

    if (!hovered) return null;
    return (
        <div
            className="pos-fixed"
            style={{
                left: mouse.x + 14,
                top: mouse.y + 14,
                zIndex: 200,
                pointerEvents: "none",
                background: "rgba(0,0,0,0.85)",
                color: "#fff",
                padding: "2px 8px",
                borderRadius: 4,
                fontSize: "0.72rem",
                fontFamily: "monospace",
            }}
        >
            {hovered.name}
        </div>
    );
}

/** Pinned info panel with the resolved numbers + copy button. */
function InspectionPanel() {
    const { pinned, setPinned } = useViewportState();
    const source = useKeypointsSource();
    const [models, setModels] = useState<ModelDefinition[] | null>(null);
    const [, setTick] = useState(0);

    useEffect(() => {
        const unsub = source.subscribeToModels ? source.subscribeToModels((m) => setModels(m)) : () => {};
        const existing = source.getModels?.();
        if (existing) setModels(existing);
        return unsub;
    }, [source]);

    // Re-resolve the numbers on a timer so a pinned panel tracks the live subject.
    useEffect(() => {
        if (!pinned) return;
        const id = setInterval(() => setTick((t) => t + 1), 100);
        return () => clearInterval(id);
    }, [pinned]);

    const [copied, setCopied] = useState(false);

    if (!pinned) return null;
    const lines = computeDetails(pinned, source, models);
    const text = detailText(pinned, lines);

    const handleCopy = async () => {
        try {
            await navigator.clipboard.writeText(text);
            setCopied(true);
            setTimeout(() => setCopied(false), 1200);
        } catch {
            /* clipboard unavailable */
        }
    };

    return (
        <div
            className="pos-abs top-0 right-0 m-2"
            style={{ zIndex: 150, background: "rgba(0,0,0,0.88)", color: "#eee", borderRadius: 6, padding: 8, fontSize: "0.7rem", fontFamily: "monospace", maxWidth: 380 }}
        >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
                <span style={{ fontWeight: "bold" }}>{pinned.name} <span style={{ color: "#888" }}>({pinned.kind})</span></span>
                <span style={{ display: "flex", gap: 4 }}>
                    <button onClick={handleCopy} style={{ background: "#333", color: "#eee", border: "none", borderRadius: 3, padding: "1px 6px", cursor: "pointer", fontSize: "0.65rem" }}>
                        {copied ? "copied" : "copy"}
                    </button>
                    <button onClick={() => setPinned(null)} style={{ background: "#333", color: "#eee", border: "none", borderRadius: 3, padding: "1px 6px", cursor: "pointer", fontSize: "0.65rem" }}>
                        ×
                    </button>
                </span>
            </div>
            {lines.map((l) => (
                <div key={l.label} style={{ marginTop: 2 }}>
                    <span style={{ color: "#aaa" }}>{l.label}:</span> {l.value}
                </div>
            ))}
        </div>
    );
}

export function ViewportInspection() {
    return (
        <>
            <HoverTooltip />
            <InspectionPanel />
        </>
    );
}
