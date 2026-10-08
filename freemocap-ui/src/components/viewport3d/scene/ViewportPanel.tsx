import { useCallback, useEffect, useRef, useState } from "react";
import clsx from "clsx";
import { useViewportState } from "./ViewportStateContext";
import { useRecordingSelection, type RecordingSelection } from "../RecordingSelectionContext";
import { LAYER_GROUPS, type LayerGroup, type LayerSpec, type LayerSwatch } from "./layer-catalog";
import {
    DEFAULT_VISIBILITY,
    type CountedLayerKey,
    type LayerKey,
    type ViewportVisibility,
} from "../helpers/viewport3d-types";

const PANEL_OPEN_STORAGE_KEY = "freemocap.viewport3d.panelOpen";
const COUNT_REFRESH_MS = 500;

/** The viewport's one collapsible top-left panel: which recording result is shown
 *  (playback only), then every layer with a legend swatch, a live count and a switch. */
export function ViewportPanel() {
    const { visibility, setVisibility } = useViewportState();
    const recording = useRecordingSelection();
    const [open, setOpen] = useState<boolean>(() => localStorage.getItem(PANEL_OPEN_STORAGE_KEY) === "true");

    useEffect(() => {
        localStorage.setItem(PANEL_OPEN_STORAGE_KEY, String(open));
    }, [open]);

    const toggle = useCallback(
        (key: LayerKey) => setVisibility((prev) => ({ ...prev, [key]: !prev[key] })),
        [setVisibility],
    );
    const resetToDefaults = useCallback(() => setVisibility(DEFAULT_VISIBILITY), [setVisibility]);

    const groups = LAYER_GROUPS;
    const isDefault = (Object.keys(DEFAULT_VISIBILITY) as LayerKey[]).every(
        (key) => visibility[key] === DEFAULT_VISIBILITY[key],
    );

    return (
        <section className={clsx("vp-layers", open && "is-open")} aria-label="Viewport">
            <button
                type="button"
                className="vp-layers-header"
                aria-expanded={open}
                onClick={() => setOpen((o) => !o)}
            >
                <span className="vp-layers-title">Viewport</span>
                <span className="vp-chevron" aria-hidden="true" />
            </button>

            {open && (
                <div className="vp-layers-body">
                    {recording !== null && <RecordingSection recording={recording} />}
                    {groups.map((group) => (
                        <LayerGroupSection key={group.id} group={group} visibility={visibility} onToggle={toggle} />
                    ))}
                    <div className="vp-layers-footer">
                        <button type="button" className="vp-link-button" disabled={isDefault} onClick={resetToDefaults}>
                            Reset to defaults
                        </button>
                    </div>
                </div>
            )}
        </section>
    );
}

/** Which saved result and sensor group the viewport is playing. */
function RecordingSection({ recording }: { recording: RecordingSelection }) {
    return (
        <div className="vp-layer-group" role="group" aria-label="Recording">
            <div className="vp-layer-group-title">
                <span>Recording</span>
                <button type="button" className="vp-link-button" onClick={recording.reload} title="Re-read the results saved for this recording">
                    Reload
                </button>
            </div>
            <label className="vp-field">
                <span className="vp-field-label">Result</span>
                <select
                    className="vp-select"
                    value={recording.runId ?? ""}
                    onChange={(e) => recording.selectRun(Number(e.target.value))}
                >
                    {recording.runIds.map((id) => (
                        <option key={id} value={id}>
                            Run {id}
                        </option>
                    ))}
                </select>
            </label>
            <label className="vp-field">
                <span className="vp-field-label">Sensor group</span>
                <select
                    className="vp-select"
                    value={recording.group}
                    title={recording.group}
                    onChange={(e) => recording.selectGroup(e.target.value)}
                >
                    {recording.groups.map((name) => (
                        <option key={name} value={name}>
                            {name}
                        </option>
                    ))}
                </select>
            </label>
            {recording.units !== null && (
                <div className="vp-field">
                    <span className="vp-field-label">Units</span>
                    <span className="vp-field-value">{recording.units}</span>
                </div>
            )}
        </div>
    );
}

function LayerGroupSection({
    group,
    visibility,
    onToggle,
}: {
    group: LayerGroup;
    visibility: ViewportVisibility;
    onToggle: (key: LayerKey) => void;
}) {
    return (
        <div className="vp-layer-group" role="group" aria-label={group.title}>
            <div className="vp-layer-group-title">{group.title}</div>
            {group.layers.map((spec) => (
                <div key={spec.key}>
                    <LayerRow spec={spec} checked={visibility[spec.key]} disabled={false} nested={false} onToggle={onToggle} />
                    {spec.children.map((child) => (
                        <LayerRow
                            key={child.key}
                            spec={child}
                            checked={visibility[child.key]}
                            disabled={!visibility[spec.key]}
                            nested={true}
                            onToggle={onToggle}
                        />
                    ))}
                </div>
            ))}
        </div>
    );
}

function LayerRow({
    spec,
    checked,
    disabled,
    nested,
    onToggle,
}: {
    spec: LayerSpec;
    checked: boolean;
    disabled: boolean;
    nested: boolean;
    onToggle: (key: LayerKey) => void;
}) {
    const active = checked && !disabled;
    return (
        <button
            type="button"
            role="switch"
            aria-checked={checked}
            disabled={disabled}
            title={spec.description}
            className={clsx("vp-layer-row", nested && "is-nested", !active && "is-off")}
            onClick={() => onToggle(spec.key)}
        >
            <Swatch swatch={spec.swatch} />
            <span className="vp-layer-label">{spec.label}</span>
            {spec.countKey !== null && active && <LiveCount countKey={spec.countKey} />}
            <span className={clsx("icon toggle-container", checked ? "on" : "off")} aria-hidden="true">
                <span className="icon toggle-circle" />
            </span>
        </button>
    );
}

function Swatch({ swatch }: { swatch: LayerSwatch | null }) {
    if (swatch === null) return <span className="vp-swatch is-empty" aria-hidden="true" />;
    const stops = swatch.colors.flatMap((color, i) => {
        const from = (i / swatch.colors.length) * 100;
        const to = ((i + 1) / swatch.colors.length) * 100;
        return [`${color} ${from}%`, `${color} ${to}%`];
    });
    return (
        <span
            className={clsx("vp-swatch", `is-${swatch.shape}`)}
            style={{ background: `linear-gradient(90deg, ${stops.join(", ")})` }}
            aria-hidden="true"
        />
    );
}

/** A count the renderers update every frame, polled into the DOM without re-rendering React. */
function LiveCount({ countKey }: { countKey: CountedLayerKey }) {
    const { statsRef } = useViewportState();
    const ref = useRef<HTMLSpanElement>(null);

    useEffect(() => {
        const write = () => {
            const el = ref.current;
            if (el) el.textContent = String(statsRef.current[countKey]);
        };
        write();
        const id = setInterval(write, COUNT_REFRESH_MS);
        return () => clearInterval(id);
    }, [statsRef, countKey]);

    return <span ref={ref} className="vp-layer-count" />;
}
