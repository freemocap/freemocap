import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { recordingCompletionDismissed } from '@/store/slices/recording/recording-slice';
import { useElectronIPC } from '@/services/electron-ipc/electron-ipc';
import type { RecordingCompletionData, StatsSummary } from '@/store/slices/recording/recording-types';
import ButtonSm from '@/components/ui-components/ButtonSm';
import SubactionHeader from '@/components/ui-components/SubactionHeader';

function formatStat(value: number, precision = 3): string {
    return value.toFixed(precision);
}

interface TimingRow { label: string; stats: StatsSummary; }

function TimingStatsTable({ data }: { data: RecordingCompletionData }) {
    const rows: TimingRow[] = [
        { label: 'Framerate / FPS (Hz)', stats: data.framerate_stats },
        { label: 'Frame Duration (ms)', stats: data.frame_duration_stats },
        { label: 'Inter-Camera Grab Sync (ms)', stats: data.inter_camera_grab_range_ms_stats },
    ];

    return (
        <div className="stats-table-wrapper">
            <table className="stats-table">
                <thead>
                    <tr>
                        <th className="stats-th" style={{ textAlign: 'left' }}>Metric</th>
                        <th className="stats-th">Median</th>
                        <th className="stats-th">Mean</th>
                        <th className="stats-th">Std</th>
                        <th className="stats-th">Min</th>
                        <th className="stats-th">Max</th>
                    </tr>
                    <tr className="stats-divider"><td colSpan={6} /></tr>
                </thead>
                <tbody>
                    {rows.map((row) => (
                        <tr key={row.label}>
                            <td className="stats-td" style={{ textAlign: 'left' }}>{row.label}</td>
                            <td className="stats-td">{formatStat(row.stats.median)}</td>
                            <td className="stats-td">{formatStat(row.stats.mean)}</td>
                            <td className="stats-td">{formatStat(row.stats.std)}</td>
                            <td className="stats-td">{formatStat(row.stats.min)}</td>
                            <td className="stats-td">{formatStat(row.stats.max)}</td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}

export const RecordingCompleteDialog: React.FC = () => {
    const dispatch = useAppDispatch();
    const navigate = useNavigate();
    const { api } = useElectronIPC();
    const completionData = useAppSelector((state) => state.recording.completionData);

    useEffect(() => {
        if (!completionData) return;
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Escape') dispatch(recordingCompletionDismissed());
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [completionData, dispatch]);

    if (!completionData) return null;

    const handleClose = () => dispatch(recordingCompletionDismissed());

    const handleCopyPath = () => {
        navigator.clipboard.writeText(completionData.recording_path);
    };

    const handleOpenFolder = async () => {
        try {
            await api?.fileSystem.openFolder.mutate({ path: completionData.recording_path });
        } catch (err) {
            console.error('Failed to open recording folder:', err);
        }
    };

    const handleOpenInPlayback = () => {
        dispatch(recordingCompletionDismissed());
        navigate('/playback', { state: { loadRecordingPath: completionData.recording_path } });
    };

    return (
        <div
            className="splash-overlay inset-0 reveal fadeIn"
            style={{ position: 'fixed', zIndex: 50 }}
            onClick={handleClose}
        >
            <div
                className="recording-complete-modal bg-dark br-2 border-1 border-black elevated-sharp flex flex-col p-4 gap-3"
                style={{ minWidth: 360, maxWidth: 520, maxHeight: '80vh', overflowY: 'auto' }}
                onClick={(e) => e.stopPropagation()}
            >
                {/* Header */}
                <div className="flex justify-content-space-between items-center">
                    <p className="text bg text-white">Recording Complete!</p>
                    <button className="button icon-button" onClick={handleClose}>
                        <span className="icon close-icon icon-size-20" />
                    </button>
                </div>

                {/* Path row */}
                <div className="flex items-center gap-1 bg-middark br-1 p-1">
                    <p className="text sm text-gray flex-1 text-nowrap overflow-hidden"
                       style={{ fontFamily: 'monospace', textOverflow: 'ellipsis' }}>
                        {completionData.recording_path}
                    </p>
                    <ButtonSm text="" iconClass="minus-icon" textColor="text-gray" onClick={handleCopyPath} title="Copy path" />
                    <ButtonSm text="" iconClass="import-icon" textColor="text-gray" onClick={handleOpenFolder} title="Open folder" />
                </div>

                {/* Summary */}
                <p className="text sm text-gray">
                    {completionData.number_of_cameras} camera{completionData.number_of_cameras !== 1 ? 's' : ''}
                    {' · '}
                    {completionData.number_of_frames} frames
                    {' · '}
                    {completionData.total_duration_sec}s
                    {' · '}
                    {completionData.mean_framerate} Hz avg
                </p>

                {/* Stats */}
                <div className="flex flex-col gap-1 bg-middark br-1 p-1">
                    <SubactionHeader text="Frame Timing Statistics" />
                    <TimingStatsTable data={completionData} />
                </div>

                {/* Actions */}
                <div className="flex gap-1 justify-content-space-between">
                    <ButtonSm
                        text="Open in Playback"
                        iconClass="subfolder-icon"
                        buttonType="secondary"
                        textColor="text-white"
                        onClick={handleOpenInPlayback}
                    />
                    <ButtonSm
                        text="Close"
                        textColor="text-gray"
                        onClick={handleClose}
                    />
                </div>
            </div>
        </div>
    );
};
