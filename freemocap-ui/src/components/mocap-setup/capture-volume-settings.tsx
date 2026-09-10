import CalibrationModule from '@/components/pipeline-progress/calibration-progress/calibration-module';
import {CalibrateRecordingButton} from '@/components/control-panels/calibration-actions/CalibrateRecordingButton';
import {useAppSelector} from '@/store';
import {selectMocapRecordingPath} from '@/store/slices/mocap/mocap-slice';
import SettingRow from '@/components/common/settings-layout/setting-row';
import ReferenceFrameSettings from './reference-frame-settings';

export default function CaptureVolumeSettings({mode}: {mode: 'recording' | 'playback'}) {
    const directory = useAppSelector(selectMocapRecordingPath);
    return <>
        <div className="capture-geometry-options">
            <CalibrationModule presentation="settings" appModeOverride={mode === 'playback' ? 'playback' : 'streaming'}/>
            <div className="recording-calibration-actions">
                <SettingRow label="Create calibration from videos" info={{title: 'Create calibration',
                    text: 'Starts a calibration pipeline using the active recording’s videos and configured board. This creates a calibration rather than loading an existing TOML.'}}
                    control={<CalibrateRecordingButton recordingPath={directory}/>}/>
            </div>
        </div>
        {mode === 'playback' && <ReferenceFrameSettings/>}
    </>;
}


