import React from 'react';
import {useAppDispatch, useAppSelector} from '@/store/hooks';
import {posthocFilterConfigUpdated} from '@/store/slices/mocap';

export function PosthocFilterConfigPanel() {
    const dispatch = useAppDispatch();
    const settings = useAppSelector(state => state.mocap.config.posthoc_filter);
    return <div className="flex flex-col gap-1 text-sm">
        <p>Recording processing uses a Butterworth low-pass filter with access to the complete recording.</p>
        <label><input type="checkbox" checked={settings.enabled}
            onChange={event => dispatch(posthocFilterConfigUpdated({enabled: event.target.checked}))}/> Enable recording filter</label>
        <label>Cutoff frequency (Hz) <input type="number" min={0.01} step="any" value={settings.cutoff}
            onChange={event => {const value = event.target.valueAsNumber; if (Number.isFinite(value) && value > 0) dispatch(posthocFilterConfigUpdated({cutoff: value}));}}/></label>
        <label>Filter order <input type="number" min={1} max={10} step={1} value={settings.order}
            onChange={event => {const value = event.target.valueAsNumber; if (Number.isInteger(value) && value > 0 && value <= 10) dispatch(posthocFilterConfigUpdated({order: value}));}}/></label>
        <p>The cutoff must be below half the recording's frame rate; the processing API validates it against the recording.</p>
    </div>;
}
