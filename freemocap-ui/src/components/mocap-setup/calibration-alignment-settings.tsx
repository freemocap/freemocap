import {useAppDispatch, useAppSelector} from '@/store';
import {calibrationConfigUpdated} from '@/store/slices/calibration';
import {CalibrationCreationAlignmentMethodSchema} from '@/store/slices/calibration/calibration-types';
import SettingRow from '@/components/common/settings-layout/setting-row';
import SettingToggleSwitch from '@/components/common/settings-layout/setting-toggle-switch';

export default function CalibrationAlignmentSettings({
    disabled = false,
}: {disabled?: boolean}) {
    const dispatch = useAppDispatch();
    const method = useAppSelector(state => state.calibration.config.alignmentMethod);
    const charuco = CalibrationCreationAlignmentMethodSchema.enum.charuco;
    return <SettingRow
        label="Align to ChArUco ground plane"
        info={{
            title: 'ChArUco calibration alignment',
            text: <p>Use the initial board pose to define the reference frame when creating
                a calibration. Place the board on the floor, a desktop, or another stable
                surface. This setting does not change an already loaded calibration.</p>,
        }}
        control={<SettingToggleSwitch
            label="Align to ChArUco ground plane"
            isToggled={method === charuco}
            disabled={disabled}
            onToggle={enabled => dispatch(calibrationConfigUpdated({
                alignmentMethod: enabled ? charuco : null,
            }))}
        />}
    />;
}

