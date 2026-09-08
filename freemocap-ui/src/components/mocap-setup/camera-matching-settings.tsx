import ToggleComponent from '@/components/ui-components/ToggleComponent';
import {CameraMatchingOptions, MatchingFailurePolicy} from '@/types/camera-matching';

interface CameraMatchingSettingsProps {
    config: CameraMatchingOptions;
    onChange: (config: CameraMatchingOptions) => void;
    showFailurePolicy: boolean;
}

export default function CameraMatchingSettings({config, onChange, showFailurePolicy}: CameraMatchingSettingsProps) {
    return <>
        <ToggleComponent
            text="Automatically match cameras to calibration"
            isToggled={config.automatically_match}
            onToggle={automatically_match => onChange({...config, automatically_match})}
        />
        {showFailurePolicy && <ToggleComponent
            text="Continue processing when camera matching fitness is poor"
            isToggled={config.failure_policy === MatchingFailurePolicy.Continue}
            onToggle={continueProcessing => onChange({...config, failure_policy:
                continueProcessing ? MatchingFailurePolicy.Continue : MatchingFailurePolicy.Stop})}
        />}
    </>;
}
