import {useAppDispatch, useAppSelector} from '@/store/hooks';
import {posthocFilterConfigUpdated, selectPosthocFilterConfig} from '@/store/slices/mocap';
import ValueSelector from '@/components/ui-components/ValueSelector';
import SettingRow from '@/components/common/settings-layout/setting-row';
import SettingsGroupHeading from '@/components/common/settings-layout/settings-group-heading';

const SAMPLING_RATE_INFO = {
    title: "Sampling rate",
    text: <>
        <p>Frames per second of the recording being filtered. It sets the Nyquist limit, so the <strong>cutoff can never exceed half of it</strong>.</p>
        <p><em>Lowering it clamps a cutoff that no longer fits.</em></p>
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
        <p>Applied to the reconstructed 3D trajectories after triangulation, to remove the frame-to-frame jitter that triangulation leaves behind.</p>
        <p>Butterworth is chosen for its flat passband: it attenuates above the cutoff without rippling the motion below it.</p>
        <p><em>Filtering runs on the whole trajectory at once, so it is a post-processing step and does not affect the realtime view.</em></p>
    </>,
};

export default function PosthocFilterSettings() {
    const dispatch = useAppDispatch();
    const config = useAppSelector(selectPosthocFilterConfig);
    const maximumCutoff = Math.max(0.1, config.sampling_rate / 2 - 0.1);

    return <>
        <SettingsGroupHeading text="Butterworth low-pass filter" info={FILTER_GROUP_INFO}/>
        <SettingRow label="Sampling rate" info={SAMPLING_RATE_INFO}
            control={<ValueSelector value={config.sampling_rate} min={1.0} max={1200.0} step={1} unit="Hz"
                onChange={sampling_rate => {
                    const newMaximumCutoff = Math.max(0.1, sampling_rate / 2 - 0.1);
                    dispatch(posthocFilterConfigUpdated({
                        sampling_rate,
                        cutoff: Math.min(config.cutoff, newMaximumCutoff),
                    }));
                }}/>}/>
        <SettingRow label="Cutoff" info={CUTOFF_INFO}
            control={<ValueSelector value={config.cutoff} min={0} max={maximumCutoff} step={1} unit="Hz"
                onChange={cutoff => dispatch(posthocFilterConfigUpdated({cutoff}))}/>}/>
        <SettingRow label="Order" info={ORDER_INFO}
            control={<ValueSelector value={config.order} min={1} max={100} step={1} unit=""
                onChange={order => dispatch(posthocFilterConfigUpdated({order}))}/>}/>
    </>;
}
