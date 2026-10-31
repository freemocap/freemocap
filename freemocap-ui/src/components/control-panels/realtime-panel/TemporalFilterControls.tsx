import React, {useEffect, useState} from 'react';
import {useTemporalFiltering} from '@/hooks/useTemporalFiltering';
import {TemporalConfigSchema, type TemporalConfig, type OneEuroConfig} from '@/types/temporal-config';

function NumericSetting({label, value, applied, unit, onChange, min = 0, max, step = 'any'}: {
    label: string; value: number; applied?: number; unit: string; onChange: (value: number) => void;
    min?: number; max?: number; step?: number | 'any';
}) {
    return <label className="flex flex-col gap-1 text-sm">
        <span>{label} ({unit})</span>
        <span className="flex flex-row gap-1 items-center">
            <input type="number" aria-label={`${label} (${unit})`} value={Number.isFinite(value) ? value : ''}
                min={min} max={max} step={step} onChange={event => onChange(event.currentTarget.valueAsNumber)}
                style={{width: 100, color: 'var(--color-text-primary)', background: 'var(--color-background-secondary)'}}/>
            <small>Applied: {applied === undefined ? '—' : Number(applied.toPrecision(6))} {unit}</small>
        </span>
    </label>;
}

export function TemporalFilterControls() {
    const {config, status, pending, apply, isConnected, loading, error, retry} = useTemporalFiltering();
    const [draft, setDraft] = useState<TemporalConfig | undefined>(config);
    const [dirty, setDirty] = useState(false);
    useEffect(() => { if (!dirty) setDraft(config); }, [config, dirty]);
    if (!draft) return <div role="status">{error ?? 'Loading filter settings from the server…'}
        <button className="button sm" onClick={retry}>Retry settings</button></div>;
    const update = (change: Partial<TemporalConfig>) => { setDraft({...draft, ...change}); setDirty(true); };
    const applied = status?.applied;
    const validation = TemporalConfigSchema.safeParse(draft);
    const smoothingControls = (key: 'image_smoothing' | 'spatial_smoothing', label: string, coordinateUnit: string) => {
        const settings = draft[key];
        const change = (patch: Partial<OneEuroConfig>) => update({[key]: {...settings, ...patch}});
        return <fieldset className="flex flex-col gap-1">
            <legend>{label}</legend>
            <label><input type="checkbox" checked={settings.enabled} onChange={event => change({enabled: event.target.checked})}/>
                {' '}Enable smoothing (applied: {applied ? String(applied[key].enabled) : '—'})</label>
            <NumericSetting label="Minimum cutoff" unit="Hz" value={settings.min_cutoff} applied={applied?.[key].min_cutoff}
                min={0.001} onChange={value => change({min_cutoff: value})}/>
            <NumericSetting label="Speed response" unit={`1/${coordinateUnit}`} value={settings.beta} applied={applied?.[key].beta}
                onChange={value => change({beta: value})}/>
            <NumericSetting label="Derivative cutoff" unit="Hz" value={settings.d_cutoff} applied={applied?.[key].d_cutoff}
                min={0.001} onChange={value => change({d_cutoff: value})}/>
        </fieldset>;
    };
    const durationSetting = (key: 'gap_duration_s' | 'prediction_duration_s' | 'velocity_half_life_s' | 'segment_retention_s' | 'reacquisition_timeout_s', label: string) =>
        <NumericSetting label={label} unit="ms" value={draft[key] * 1000}
            applied={applied ? applied[key] * 1000 : undefined} min={key === 'velocity_half_life_s' || key === 'reacquisition_timeout_s' ? 1 : 0}
            max={key === 'reacquisition_timeout_s' || key === 'velocity_half_life_s' ? undefined : 2000}
            onChange={value => update({[key]: value / 1000})}/>;
    return <div className="flex flex-col gap-1">
        <p className="text-sm">2D confidence checks → optional pixel smoothing → triangulation → velocity rejection → optional 3D smoothing → timed gap recovery → skeleton fitting and continuity.</p>
        <p className="text-sm">3D thresholds use calibrated millimetres; they do not apply to single-camera pixel coordinates. Generated values never count as fresh input for body dimensions.</p>
        <fieldset disabled={loading} className="flex flex-col gap-1">
            {smoothingControls('image_smoothing', 'Image smoothing', 'px')}
            {smoothingControls('spatial_smoothing', 'Spatial smoothing', 'mm')}
            <label><input type="checkbox" checked={draft.velocity_gate_enabled}
                onChange={event => update({velocity_gate_enabled: event.target.checked})}/> Reject excessive velocity
                {' '}(applied: {applied ? String(applied.velocity_gate_enabled) : '—'})</label>
            <NumericSetting label="Maximum velocity" unit="mm/s" value={draft.max_velocity_mm_per_s}
                applied={applied?.max_velocity_mm_per_s} min={1} onChange={value => update({max_velocity_mm_per_s: value})}/>
            <NumericSetting label="Maximum reprojection error" unit="px" value={draft.max_reprojection_error_px}
                applied={applied?.max_reprojection_error_px} min={0.001} onChange={value => update({max_reprojection_error_px: value})}/>
            {durationSetting('reacquisition_timeout_s', 'Velocity rejection timeout')}
            {durationSetting('gap_duration_s', 'Point visibility limit')}
            {durationSetting('prediction_duration_s', 'Prediction motion limit')}
            {durationSetting('velocity_half_life_s', 'Prediction velocity half-life')}
            {durationSetting('segment_retention_s', 'Segment retention limit')}
            <p className="text-sm">Prediction stops moving at its motion limit; points remain held only until the visibility limit. Segment retention runs from the last supported pose, not from the last generated frame.</p>
            <NumericSetting label="Body scale window" unit="frames" value={draft.segment_scale_window_frames}
                applied={applied?.segment_scale_window_frames} min={1} step={1}
                onChange={value => update({segment_scale_window_frames: value})}/>
            <div className="flex flex-row gap-1">
                <button className="button sm" disabled={!dirty || !validation.success} onClick={async () => {
                    try { await apply(draft); setDirty(false); } catch { /* Redux displays the API error below. */ }
                }}>{isConnected ? 'Apply settings' : 'Save for pipeline start'}</button>
                <button className="button sm secondary" disabled={!status} onClick={() => {
                    if (status) {setDraft(status.defaults); setDirty(true);}
                }}>Load default values</button>
            </div>
        </fieldset>
        <p role="status" className="text-sm">{dirty ? 'Unsubmitted changes' : pending ? 'Waiting for the next processed frame to confirm settings' : applied ? 'Confirmed by the processing worker' : 'Settings will apply when the pipeline starts'}</p>
        {!validation.success && <p role="alert">{validation.error.issues.map(issue => `${issue.path.join('.')}: ${issue.message}`).join('; ')}</p>}
        {error && <p role="alert">{error} <button onClick={retry}>Refresh settings</button></p>}
    </div>;
}
