import React from 'react';
import {useNavigate} from 'react-router-dom';
import {useAppDispatch, useAppSelector} from '@/store/hooks';
import {recordingCompletionDismissed} from '@/store/slices/recording/recording-slice';
import {useElectronIPC} from '@/services/electron-ipc/electron-ipc';
import type {RecordingCompletionData, StatsSummary} from '@/store/slices/recording/recording-types';

function formatStat(value: number, precision: number = 3): string {
    return value.toFixed(precision);
}

interface TimingRow {
    label: string;
    stats: StatsSummary;
}

function TimingStatsTable({ data }: { data: RecordingCompletionData }) {
    const rows: TimingRow[] = [
        { label: 'Framerate / FPS (Hz)', stats: data.framerate_stats },
        { label: 'Frame Duration (ms)', stats: data.frame_duration_stats },
        { label: 'Inter-Camera Frame Grab Sync (ms)', stats: data.inter_camera_grab_range_ms_stats },
    ];

    const thStyle: React.CSSProperties = {fontWeight: 'bold', padding: '4px 8px', fontSize: '0.8rem', textAlign: 'left', borderBottom: '1px solid var(--color-border-secondary)'};
    const tdStyle: React.CSSProperties = {padding: '4px 8px', fontSize: '0.8rem'};
    const tdRightStyle: React.CSSProperties = {...tdStyle, textAlign: 'right'};

    return (
        <table className="w-full" style={{borderCollapse: 'collapse'}}>
            <thead>
                <tr>
                    <th style={thStyle}>Metric</th>
                    <th style={{...thStyle, textAlign: 'right'}}>Median</th>
                    <th style={{...thStyle, textAlign: 'right'}}>Mean</th>
                    <th style={{...thStyle, textAlign: 'right'}}>Std</th>
                    <th style={{...thStyle, textAlign: 'right'}}>Min</th>
                    <th style={{...thStyle, textAlign: 'right'}}>Max</th>
                </tr>
            </thead>
            <tbody>
                {rows.map((row) => (
                    <tr key={row.label}>
                        <td style={tdStyle}>{row.label}</td>
                        <td style={tdRightStyle}>{formatStat(row.stats.median)}</td>
                        <td style={tdRightStyle}>{formatStat(row.stats.mean)}</td>
                        <td style={tdRightStyle}>{formatStat(row.stats.std)}</td>
                        <td style={tdRightStyle}>{formatStat(row.stats.min)}</td>
                        <td style={tdRightStyle}>{formatStat(row.stats.max)}</td>
                    </tr>
                ))}
            </tbody>
        </table>
    );
}

export const RecordingCompleteDialog: React.FC = () => {
    const dispatch = useAppDispatch();
    const navigate = useNavigate();
    const { api } = useElectronIPC();
    const completionData = useAppSelector((state) => state.recording.completionData);

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
            className="splash-overlay inset-0"
            style={{position: 'fixed', zIndex: 100}}
            onClick={handleClose}
        >
            <div
                className="pos-rel bg-middark br-2 flex flex-col p-3 w-full"
                style={{minWidth: 480, maxWidth: 720}}
                onClick={(e) => e.stopPropagation()}
            >
                <div className="flex flex-row items-center justify-content-space-between pb-2">
                    <p className="text bg text-white">Recording Complete!</p>
                    <button className="button icon-button br-1" onClick={handleClose} title="Close">
                        <span className="icon close-icon icon-size-20" />
                    </button>
                </div>

                <div className="flex flex-row items-center gap-1 mb-2">
                    <span
                        className="text sm text-gray br-1 flex-1 overflow-hidden"
                        style={{
                            fontFamily: 'monospace',
                            fontSize: '0.8rem',
                            backgroundColor: 'var(--color-bg-elevated)',
                            padding: '4px 8px',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                        }}
                    >
                        {completionData.recording_path}
                    </span>
                    <button className="button icon-button br-1" onClick={handleCopyPath} title="Copy path">
                        <span className="icon copy-icon icon-size-20" />
                    </button>
                    <button className="button icon-button br-1" onClick={handleOpenFolder} title="Open folder">
                        <span className="icon folder-icon icon-size-20" />
                    </button>
                </div>

                <p className="text sm text-gray mb-2">
                    {completionData.number_of_cameras} camera{completionData.number_of_cameras !== 1 ? 's' : ''}
                    {' · '}
                    {completionData.number_of_frames} frames
                    {' · '}
                    {completionData.total_duration_sec}s
                    {' · '}
                    {completionData.mean_framerate} Hz avg
                </p>

                <div style={{height: 1, backgroundColor: 'var(--color-border-secondary)', margin: '4px 0 8px 0'}} />

                <p className="text sm text-white mb-2" style={{fontWeight: 600}}>
                    Frame Timing Statistics
                </p>

                <TimingStatsTable data={completionData} />

                <div className="flex flex-row gap-1 mt-3 flex-end">
                    <button className="button sm secondary" onClick={handleOpenInPlayback}>
                        <span className="icon play-icon icon-size-20 mr-1" />
                        Open in Playback
                    </button>
                    <button className="button sm primary" onClick={handleClose}>
                        Close
                    </button>
                </div>
            </div>
        </div>
    );
};
