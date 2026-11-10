import React, {useEffect, useState, type ReactNode} from 'react';
import {useTemporalFiltering} from '@/hooks/useTemporalFiltering';
import {TemporalConfigSchema, type TemporalConfig, type OneEuroConfig} from '@/types/temporal-config';
import SettingRow from '@/components/common/settings-layout/setting-row';
import SettingsGroupHeading from '@/components/common/settings-layout/settings-group-heading';
import SettingToggleSwitch from '@/components/common/settings-layout/setting-toggle-switch';
import SettingsSummaryChip from '@/components/common/settings-layout/settings-summary-chip';
import DependentRowGroup from '@/components/common/settings-layout/dependent-row-group';
import ValueSelector from '@/components/ui-components/ValueSelector';
import ButtonSm from '@/components/ui-components/ButtonSm';
import '@/components/pipeline-progress/realtime/realtime-settings.css';

type Info = {title: string; text: ReactNode};
type SmoothingKey = 'image_smoothing' | 'spatial_smoothing';
type DurationKey = 'gap_duration_s' | 'prediction_duration_s' | 'velocity_half_life_s' | 'segment_retention_s' | 'reacquisition_timeout_s';

// Tune slow-motion jitter with the minimum cutoff first, then fast-motion lag
// with the speed response [@casiezOneEuroTuning].
const ONE_EURO_TUNING = <p><em>Tune with slow movement first: lower the minimum cutoff until jitter is acceptable.
    Then, with fast movement, raise the speed response until lag is acceptable.</em></p>;

const SMOOTHING = {
    image_smoothing: {
        name: 'Image smoothing', switchLabel: 'Smooth image keypoints', unit: 'px',
        info: {title: 'Image smoothing', text: <>
            <p>A One Euro filter on each camera's 2D keypoints, in pixels, before triangulation. Off by default.</p>
            {ONE_EURO_TUNING}
        </>},
    },
    spatial_smoothing: {
        name: 'Spatial smoothing', switchLabel: 'Smooth 3D keypoints', unit: 'mm',
        info: {title: 'Spatial smoothing', text: <>
            <p>A One Euro filter on the triangulated 3D keypoints, in millimetres, after velocity rejection.
                The smoothing button in the toolbar switches it on and off.</p>
            {ONE_EURO_TUNING}
        </>},
    },
} as const;

const OUTLIER_INFO: Info = {title: 'Outlier rejection', text: <>
    <p>Rejects implausible points before they are smoothed or fitted.</p>
    <p><em>3D thresholds use calibrated millimetres; they do not apply to single-camera pixel coordinates.</em></p>
</>};
const REPROJECTION_INFO: Info = {title: 'Reprojection error limit',
    text: <p>Triangulated points whose mean reprojection error exceeds this many pixels are rejected.</p>};
const VELOCITY_GATE_INFO: Info = {title: 'Velocity rejection',
    text: <p>Holds a 3D point at its last accepted position when it moves faster than the maximum velocity, so a
        single-frame jump does not reach the skeleton.</p>};
const MAX_VELOCITY_INFO: Info = {title: 'Velocity limit',
    text: <p>The fastest movement accepted as real, in millimetres per second.</p>};
const REACQUISITION_INFO: Info = {title: 'Velocity rejection timeout',
    text: <p>After a point has been held this long, its next measurement is accepted at any speed, so a point
        that really moved is picked up again.</p>};
const GAP_INFO: Info = {title: 'Gap recovery', text: <>
    <p>A point that stops receiving accepted measurements keeps moving along its predicted velocity, then holds
        still, then disappears.</p>
    <p><em>Prediction stops moving at its motion limit; points remain held only until the visibility limit.</em></p>
</>};
const VISIBILITY_INFO: Info = {title: 'Visibility limit', text: <p>How long a lost point stays visible (predicted,
    then held) after its last accepted measurement. Zero turns gap recovery off.</p>};
const PREDICTION_INFO: Info = {title: 'Motion limit',
    text: <p>How long a lost point keeps moving along its predicted velocity before it holds its position.</p>};
const HALF_LIFE_INFO: Info = {title: 'Velocity half-life',
    text: <p>The predicted velocity halves every this many milliseconds, so a prediction slows down instead of drifting.</p>};
const CONTINUITY_INFO: Info = {title: 'Skeleton continuity',
    text: <p>How the fitted skeleton carries through missing data. Generated values never count as fresh input for
        body dimensions.</p>};
const RETENTION_INFO: Info = {title: 'Retention limit', text: <p>How long a body segment keeps its last supported
    pose when its points are lost. It runs from the last supported pose, not from the last generated frame.</p>};
const SCALE_WINDOW_INFO: Info = {title: 'Scale window',
    text: <p>How many recent frames are used to estimate segment lengths when fitting the skeleton.</p>};

const toMs = (seconds: number) => Math.round(seconds * 1e6) / 1e3;
const formatNumber = (value: number) => String(Number(value.toPrecision(6)));

/** The value the processing worker is running, shown only where it differs from the draft. */
function AppliedChip({draft, applied, unit = ''}: {draft: number | boolean; applied?: number | boolean; unit?: string}) {
    if (applied === undefined || applied === draft) return null;
    const value = typeof applied === 'boolean' ? (applied ? 'on' : 'off') : `${formatNumber(applied)}${unit && ` ${unit}`}`;
    return <SettingsSummaryChip tone="caution" title="The value the processing worker is using now">applied {value}</SettingsSummaryChip>;
}

function NumberRow({label, ariaLabel, info, unit, value, applied, min, max, step, inactive = false, onChange}: {
    label: string; ariaLabel?: string; info: Info; unit: string; value: number; applied?: number;
    min: number; max: number; step: number; inactive?: boolean; onChange: (value: number) => void;
}) {
    return <SettingRow label={<>{label}<AppliedChip draft={value} applied={applied} unit={unit}/></>} info={info} inactive={inactive}
        control={<ValueSelector ariaLabel={`${ariaLabel ?? label} (${unit})`} value={value} min={min} max={max} step={step}
            unit={unit} disabled={inactive} onChange={onChange}/>}/>;
}

/** Realtime filter settings: edited as a draft, submitted together, confirmed by the processing worker. */
export function TemporalFilterControls() {
    const {config, status, pending, apply, isConnected, loading, error, retry} = useTemporalFiltering();
    const [draft, setDraft] = useState<TemporalConfig | undefined>(config);
    const [dirty, setDirty] = useState(false);
    useEffect(() => { if (!dirty) setDraft(config); }, [config, dirty]);
    if (!draft) return <div role="status" className="settings-note">
        {error ?? 'Loading filter settings from the server…'}
        <ButtonSm text="Retry settings" buttonType="secondary" textColor="text-white" onClick={retry}/>
    </div>;
    const update = (change: Partial<TemporalConfig>) => { setDraft({...draft, ...change}); setDirty(true); };
    const applied = status?.applied ?? undefined;
    const validation = TemporalConfigSchema.safeParse(draft);

    const smoothingRows = (key: SmoothingKey) => {
        const {name, switchLabel, unit, info} = SMOOTHING[key];
        const settings = draft[key];
        const off = !settings.enabled;
        const change = (patch: Partial<OneEuroConfig>) => update({[key]: {...settings, ...patch}});
        return <>
            <SettingsGroupHeading text={name} info={info}/>
            <SettingRow label={<>{switchLabel}<AppliedChip draft={settings.enabled} applied={applied?.[key].enabled}/></>}
                info={info}
                control={<SettingToggleSwitch label={switchLabel} isToggled={settings.enabled} onToggle={enabled => change({enabled})}/>}/>
            <DependentRowGroup>
                <NumberRow label="Minimum cutoff" ariaLabel={`${name} minimum cutoff`} unit="Hz" inactive={off}
                    info={{title: `${name}: minimum cutoff`, text: <p>The cutoff frequency while a point is still. Lower values
                        remove more jitter from slow movement and add more lag.</p>}}
                    value={settings.min_cutoff} applied={applied?.[key].min_cutoff} min={0.01} max={100} step={0.05}
                    onChange={value => change({min_cutoff: value})}/>
                <NumberRow label="Speed response" ariaLabel={`${name} speed response`} unit={`1/${unit}`} inactive={off}
                    info={{title: `${name}: speed response`, text: <p>How fast the cutoff rises with speed (the One Euro β).
                        Higher values reduce lag in fast movement and let through more jitter.</p>}}
                    value={settings.beta} applied={applied?.[key].beta} min={0} max={10} step={0.0005}
                    onChange={value => change({beta: value})}/>
                <NumberRow label="Derivative cutoff" ariaLabel={`${name} derivative cutoff`} unit="Hz" inactive={off}
                    info={{title: `${name}: derivative cutoff`, text: <p>The cutoff for the speed estimate that drives the
                        speed response. Usually left at 1 Hz.</p>}}
                    value={settings.d_cutoff} applied={applied?.[key].d_cutoff} min={0.01} max={100} step={0.05}
                    onChange={value => change({d_cutoff: value})}/>
            </DependentRowGroup>
        </>;
    };

    const durationRow = (key: DurationKey, label: string, info: Info, min: number, max: number, inactive = false) =>
        <NumberRow label={label} unit="ms" info={info} inactive={inactive} value={toMs(draft[key])}
            applied={applied ? toMs(applied[key]) : undefined} min={min} max={max} step={10}
            onChange={value => update({[key]: value / 1000})}/>;

    const statusText = dirty ? 'Unsubmitted changes'
        : pending ? 'Waiting for the next processed frame to confirm settings'
        : applied ? 'Confirmed by the processing worker'
        : 'Settings will apply when the pipeline starts';

    return <>
        <fieldset disabled={loading} className="realtime-filter-fields">
            {smoothingRows('image_smoothing')}

            <SettingsGroupHeading text="Outlier rejection" info={OUTLIER_INFO}/>
            <NumberRow label="Maximum reprojection error" unit="px" info={REPROJECTION_INFO}
                value={draft.max_reprojection_error_px} applied={applied?.max_reprojection_error_px}
                min={0.5} max={1000} step={0.5} onChange={value => update({max_reprojection_error_px: value})}/>
            <SettingRow label={<>Reject excessive velocity<AppliedChip draft={draft.velocity_gate_enabled} applied={applied?.velocity_gate_enabled}/></>}
                info={VELOCITY_GATE_INFO}
                control={<SettingToggleSwitch label="Reject excessive velocity" isToggled={draft.velocity_gate_enabled}
                    onToggle={enabled => update({velocity_gate_enabled: enabled})}/>}/>
            <DependentRowGroup>
                <NumberRow label="Maximum velocity" unit="mm/s" info={MAX_VELOCITY_INFO} inactive={!draft.velocity_gate_enabled}
                    value={draft.max_velocity_mm_per_s} applied={applied?.max_velocity_mm_per_s}
                    min={1} max={1000000} step={500} onChange={value => update({max_velocity_mm_per_s: value})}/>
                {durationRow('reacquisition_timeout_s', 'Velocity rejection timeout', REACQUISITION_INFO, 1, 10000, !draft.velocity_gate_enabled)}
            </DependentRowGroup>

            {smoothingRows('spatial_smoothing')}

            <SettingsGroupHeading text="Gap recovery" info={GAP_INFO}/>
            {durationRow('gap_duration_s', 'Point visibility limit', VISIBILITY_INFO, 0, 2000)}
            <DependentRowGroup>
                {durationRow('prediction_duration_s', 'Prediction motion limit', PREDICTION_INFO, 0, 2000, draft.gap_duration_s === 0)}
                {durationRow('velocity_half_life_s', 'Prediction velocity half-life', HALF_LIFE_INFO, 1, 10000, draft.gap_duration_s === 0)}
            </DependentRowGroup>

            <SettingsGroupHeading text="Skeleton continuity" info={CONTINUITY_INFO}/>
            {durationRow('segment_retention_s', 'Segment retention limit', RETENTION_INFO, 0, 2000)}
            <NumberRow label="Body scale window" unit="frames" info={SCALE_WINDOW_INFO}
                value={draft.segment_scale_window_frames} applied={applied?.segment_scale_window_frames}
                min={1} max={3000} step={1} onChange={value => update({segment_scale_window_frames: value})}/>
        </fieldset>

        <div className="realtime-settings-actions">
            <p role="status" className="settings-note">{statusText}</p>
            {!validation.success && <p role="alert" className="settings-note settings-note-error">
                {validation.error.issues.map(issue => `${issue.path.join('.')}: ${issue.message}`).join('; ')}</p>}
            {error && <div role="alert" className="settings-note settings-note-error">{error}
                <ButtonSm text="Refresh settings" buttonType="secondary" textColor="text-white" onClick={retry}/></div>}
            <div className="realtime-settings-buttons">
                <ButtonSm text="Load default values" buttonType="secondary" textColor="text-white" disabled={!status || loading}
                    onClick={() => { if (status) {setDraft(status.defaults); setDirty(true);} }}/>
                <ButtonSm text={isConnected ? 'Apply settings' : 'Save for pipeline start'} className="primary accent"
                    textColor="text-white" disabled={!dirty || !validation.success || loading}
                    onClick={async () => {
                        try { await apply(draft); setDirty(false); } catch { /* Redux displays the API error above. */ }
                    }}/>
            </div>
        </div>
    </>;
}
