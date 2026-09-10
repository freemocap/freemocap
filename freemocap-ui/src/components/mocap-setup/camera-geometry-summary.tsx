import {useAppSelector} from '@/store';
import {CalibrationBoardMode} from '@/store/slices/calibration/calibration-types';
import SettingsSummaryChip from '@/components/common/settings-layout/settings-summary-chip';

export default function CameraGeometrySummary() {
    const calibration = useAppSelector(state => state.calibration.loadedCalibration);
    const config = useAppSelector(state => state.calibration.config);
    const alignToPerson = useAppSelector(state => state.mocap.config.bodyAlignmentEnabled);
    const filename = calibration?.path.split(/[\\/]/).pop();
    return <span className="camera-geometry-summary">
        <span className="camera-geometry-summary-values">
            <SettingsSummaryChip tone={calibration ? 'positive' : 'quiet'}>
                {calibration ? `Calibrated · ${calibration.cameras.length} cameras` : 'Select a calibration'}
            </SettingsSummaryChip>
            <SettingsSummaryChip title="Configured calibration board">
                {config.boardMode === CalibrationBoardMode.AUTO ? 'Auto board' : `${config.charucoBoard.squares_x} × ${config.charucoBoard.squares_y} board`} · {config.charucoBoard.square_length_mm} mm
            </SettingsSummaryChip>
            <SettingsSummaryChip title="Calibration solver">{config.solverMethod === 'anipose' ? 'Anipose' : 'Pyceres'}</SettingsSummaryChip>
            <SettingsSummaryChip>{calibration?.metadata?.groundplane_applied === true
                ? 'Saved ground plane' : alignToPerson ? 'Align to person' : 'Calibration frame'}</SettingsSummaryChip>
        </span>
        {calibration && <SettingsSummaryChip tone="path" title={calibration.path}>{filename}</SettingsSummaryChip>}
    </span>;
}
