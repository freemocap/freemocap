import {useEffect, useState} from 'react';
import {useAppSelector} from '@/store';
import SettingsSection from '@/components/common/settings-layout/settings-section';
import SettingsSummaryChip from '@/components/common/settings-layout/settings-summary-chip';
import CalibrationModule from '@/components/pipeline-progress/calibration-progress/calibration-module';
import {RecordingCalibrationOptions} from './RecordingCalibrationOptions';
import ReferenceFrameSettings from './reference-frame-settings';

export default function CaptureVolumeSettings({mode}: {mode: 'recording' | 'playback'}) {
    const calibration = useAppSelector(state => state.calibration.loadedCalibration);
    const [geometryExpanded, setGeometryExpanded] = useState(!calibration);
    useEffect(() => {setGeometryExpanded(!calibration);}, [calibration?.path]);
    const filename = calibration?.path.split(/[\/]/).pop() ?? '';

    return <>
        <SettingsSection nested title="Camera geometry" expanded={geometryExpanded}
            onExpandedChange={setGeometryExpanded}
            summary={calibration
                ? <>
                    <SettingsSummaryChip tone="positive">{calibration.cameras.length} cameras</SettingsSummaryChip>
                    <SettingsSummaryChip tone="path" title={calibration.path}>{filename}</SettingsSummaryChip>
                </>
                : <SettingsSummaryChip tone="quiet">Select or calibrate…</SettingsSummaryChip>}>
            <div className="capture-geometry-options">
                <CalibrationModule appModeOverride={mode === 'playback' ? 'playback' : 'streaming'}/>
                <RecordingCalibrationOptions/>
            </div>
        </SettingsSection>
        <ReferenceFrameSettings/>
    </>;
}
