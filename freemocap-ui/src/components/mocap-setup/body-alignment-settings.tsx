import {useAppDispatch, useAppSelector} from '@/store';
import {bodyAlignmentUpdated} from '@/store/slices/mocap';
import SettingRow from '@/components/common/settings-layout/setting-row';
import SettingsGroupHeading from '@/components/common/settings-layout/settings-group-heading';
import SettingToggleSwitch from '@/components/common/settings-layout/setting-toggle-switch';

const ALIGN_INFO = {
    title: 'Align to person',
    text: <>
        <p>Uses stationary foot contacts to estimate the floor and body landmarks to establish orientation. If foot support is insufficient, uses body orientation.</p>
        <p>A ground plane saved in the calibration takes precedence. Turn this off to keep the calibration frame when no ground plane is saved.</p>
        <p>Applies to the next mocap processing run, including its reconstructed points and cameras.</p>
    </>,
};

export default function BodyAlignmentSettings() {
    const dispatch = useAppDispatch();
    const enabled = useAppSelector(state => state.mocap.config.bodyAlignmentEnabled);
    return <>
        <SettingsGroupHeading text="Capture volume alignment" info={ALIGN_INFO}/>
        <SettingRow label="Align to person" info={ALIGN_INFO} control={
            <SettingToggleSwitch label="Align to person" isToggled={enabled}
                onToggle={value => dispatch(bodyAlignmentUpdated(value))}/>
        }/>

    </>;
}

