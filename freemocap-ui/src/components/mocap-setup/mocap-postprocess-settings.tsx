import {useAppDispatch, useAppSelector} from '@/store/hooks';
import {posthocFilterConfigUpdated, selectPosthocFilterConfig} from '@/store/slices/mocap';
import ValueSelector from '@/components/ui-components/ValueSelector';
import SettingRow from '@/components/common/settings-layout/setting-row';
import SettingsGroupHeading from '@/components/common/settings-layout/settings-group-heading';
import SettingToggleSwitch from '@/components/common/settings-layout/setting-toggle-switch';

const SAMPLING_RATE_INFO = {
    title: "Sampling rate",
    text: <>
        <p>Derived from the recording timestamps. Processing rejects a cutoff at or above half the resolved sampling rate.</p>
        <p>Irregular samples are filtered using their recorded times. Missing observations and long timing gaps separate trajectories.</p>
    </>,
};

const CUTOFF_INFO = {
    title: "Cutoff",
    text: <>
        <p>Motion above this frequency is treated as noise and removed.</p>
        <p><em>Lower cutoffs give smoother trajectories and can flatten fast movement; higher cutoffs keep detail and more jitter.</em></p>
    </>,
};

const ORDER_INFO = {
    title: "Order",
    text: <>
        <p>How sharply the filter rolls off at the cutoff. Higher orders separate signal from noise more decisively.</p>
        <p><em>Very high orders can ring around abrupt changes.</em></p>
    </>,
};

const FILTER_GROUP_INFO = {
    title: "Butterworth low-pass filter",
    text: <>
        <p>Applied to measured 3D trajectories after triangulation and alignment, before fitting and skeleton reconstruction.</p>
        <p>Butterworth is chosen for its flat passband: it attenuates above the cutoff without rippling the motion below it.</p>
        <p><em>Filtering runs on the whole trajectory at once, so it is a post-processing step and does not affect the realtime view.</em></p>
        <p>Missing observations remain missing. Runs too short for the filter retain their measured values; their count is saved with the processing result.</p>
    </>,
};

export default function PosthocFilterSettings() {
    const dispatch = useAppDispatch();
    const config = useAppSelector(selectPosthocFilterConfig);

    return <>
        <SettingsGroupHeading text="Butterworth low-pass filter" info={FILTER_GROUP_INFO}/>
        <SettingRow label="Filter trajectories" info={FILTER_GROUP_INFO} control={<SettingToggleSwitch label="Filter trajectories"
            isToggled={config.enabled} onToggle={enabled => dispatch(posthocFilterConfigUpdated({enabled}))}/>}/>
        <SettingRow label="Sampling rate" info={SAMPLING_RATE_INFO}
            control={<span>From recording timestamps</span>}/>
        <SettingRow label="Cutoff" info={CUTOFF_INFO} inactive={!config.enabled}
            control={<ValueSelector value={config.cutoff} min={0.1} max={600} step={0.1} unit="Hz" disabled={!config.enabled}
                onChange={cutoff => dispatch(posthocFilterConfigUpdated({cutoff}))}/>}/>
        <SettingRow label="Order" info={ORDER_INFO} inactive={!config.enabled}
            control={<ValueSelector value={config.order} min={1} max={10} step={1} unit="" disabled={!config.enabled}
                onChange={order => dispatch(posthocFilterConfigUpdated({order}))}/>}/>
    </>;
}
