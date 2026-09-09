import SettingRow from '@/components/common/settings-layout/setting-row';
import SettingToggleSwitch from '@/components/common/settings-layout/setting-toggle-switch';
import {CameraMatchingOptions, MatchingFailurePolicy} from '@/types/camera-matching';

const MATCHING_INFO = {
    title: "Camera matching",
    text: <>
        <p>Matches the cameras in this recording to the cameras in the calibration file, so rays are triangulated with the right intrinsics and pose.</p>
        <p><em>Turn it off only when the recording's camera order is already known to match the calibration.</em></p>
    </>,
};

const FAILURE_POLICY_INFO = {
    title: "Poor matching fitness",
    text: <>
        <p>When the best match between this recording's cameras and the calibration's cameras still fits badly, processing either continues with that match or stops.</p>
        <p><strong>On:</strong> processing continues. You get output, but a wrong pairing produces wrong 3D positions.</p>
        <p><strong>Off:</strong> processing stops so the calibration or the camera order can be corrected first.</p>
    </>,
};

interface CameraMatchingSettingsProps {
    config: CameraMatchingOptions;
    onChange: (config: CameraMatchingOptions) => void;
    showFailurePolicy: boolean;
}

export default function CameraMatchingSettings({config, onChange, showFailurePolicy}: CameraMatchingSettingsProps) {
    return <>
        <SettingRow label="Automatically match cameras to calibration" info={MATCHING_INFO}
            control={<SettingToggleSwitch label="Automatically match cameras to calibration"
                isToggled={config.automatically_match}
                onToggle={automatically_match => onChange({...config, automatically_match})}/>}/>
        {showFailurePolicy && <SettingRow label="Continue processing when camera matching fitness is poor"
            info={FAILURE_POLICY_INFO}
            control={<SettingToggleSwitch label="Continue processing when camera matching fitness is poor"
                isToggled={config.failure_policy === MatchingFailurePolicy.Continue}
                onToggle={continueProcessing => onChange({...config, failure_policy:
                    continueProcessing ? MatchingFailurePolicy.Continue : MatchingFailurePolicy.Stop})}/>}/>}
    </>;
}
