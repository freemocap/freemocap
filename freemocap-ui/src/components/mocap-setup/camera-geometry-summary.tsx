import {useAppSelector} from '@/store';
import {CalibrationAlignmentMethodSchema, CalibrationBoardMode, CALIBRATION_SOLVER_LABELS} from '@/store/slices/calibration/calibration-types';
import SettingsSummaryChip from '@/components/common/settings-layout/settings-summary-chip';

export default function CameraGeometrySummary() {
    const calibration = useAppSelector(state => state.calibration.loadedCalibration);
    const config = useAppSelector(state => state.calibration.config);
    const filename = calibration?.path.split(/[\\/]/).pop();
    return <span className="camera-geometry-summary">
        <span className="camera-geometry-summary-values">
            <SettingsSummaryChip tone={calibration ? 'positive' : 'quiet'}>
                {calibration ? `Calibrated · ${calibration.cameras.length} cameras` : 'Select a calibration'}
            </SettingsSummaryChip>
            <SettingsSummaryChip title="Configured calibration board">
                {config.boardMode === CalibrationBoardMode.AUTO ? 'Auto board' : `${config.charucoBoard.squares_x} × ${config.charucoBoard.squares_y} board`} · {config.charucoBoard.square_length_mm} mm
            </SettingsSummaryChip>
            <SettingsSummaryChip title="Calibration solver">{CALIBRATION_SOLVER_LABELS[config.solverMethod]}</SettingsSummaryChip>
            <SettingsSummaryChip>{config.alignmentMethod === CalibrationAlignmentMethodSchema.enum.person
                ? 'Align to person'
                : config.alignmentMethod === CalibrationAlignmentMethodSchema.enum.charuco
                    ? 'Align to ChArUco ground plane' : 'No additional alignment'}</SettingsSummaryChip>
        </span>
        {calibration && <SettingsSummaryChip tone="path" title={calibration.path}>{filename}</SettingsSummaryChip>}
    </span>;
}
