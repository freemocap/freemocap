import React from 'react';
import {
    Box,
    Button,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    Divider,
    IconButton,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Typography,
} from '@mui/material';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
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

    return (
        <TableContainer>
            <Table size="small" sx={{ '& td, & th': { py: 0.5, px: 1, fontSize: '0.8rem' } }}>
                <TableHead>
                    <TableRow>
                        <TableCell sx={{ fontWeight: 'bold' }}>Metric</TableCell>
                        <TableCell align="right" sx={{ fontWeight: 'bold' }}>Median</TableCell>
                        <TableCell align="right" sx={{ fontWeight: 'bold' }}>Mean</TableCell>
                        <TableCell align="right" sx={{ fontWeight: 'bold' }}>Std</TableCell>
                        <TableCell align="right" sx={{ fontWeight: 'bold' }}>Min</TableCell>
                        <TableCell align="right" sx={{ fontWeight: 'bold' }}>Max</TableCell>
                    </TableRow>
                </TableHead>
                <TableBody>
                    {rows.map((row) => (
                        <TableRow key={row.label}>
                            <TableCell>{row.label}</TableCell>
                            <TableCell align="right">{formatStat(row.stats.median)}</TableCell>
                            <TableCell align="right">{formatStat(row.stats.mean)}</TableCell>
                            <TableCell align="right">{formatStat(row.stats.std)}</TableCell>
                            <TableCell align="right">{formatStat(row.stats.min)}</TableCell>
                            <TableCell align="right">{formatStat(row.stats.max)}</TableCell>
                        </TableRow>
                    ))}
                </TableBody>
            </Table>
        </TableContainer>
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
        <Dialog open onClose={handleClose} maxWidth="md" fullWidth>
            <DialogTitle sx={{ pb: 1 }}>Recording Complete!</DialogTitle>
            <DialogContent>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                    <Typography
                        variant="body2"
                        sx={{
                            fontFamily: 'monospace',
                            fontSize: '0.8rem',
                            bgcolor: 'action.hover',
                            px: 1,
                            py: 0.5,
                            borderRadius: 1,
                            flex: 1,
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                        }}
                    >
                        {completionData.recording_path}
                    </Typography>
                    <IconButton size="small" onClick={handleCopyPath} title="Copy path">
                        <ContentCopyIcon fontSize="small" />
                    </IconButton>
                    <IconButton size="small" onClick={handleOpenFolder} title="Open folder">
                        <FolderOpenIcon fontSize="small" />
                    </IconButton>
                </Box>

                <Typography variant="body2" sx={{ mb: 2, color: 'text.secondary' }}>
                    {completionData.number_of_cameras} camera{completionData.number_of_cameras !== 1 ? 's' : ''}
                    {' \u00B7 '}
                    {completionData.number_of_frames} frames
                    {' \u00B7 '}
                    {completionData.total_duration_sec}s
                    {' \u00B7 '}
                    {completionData.mean_framerate} Hz avg
                </Typography>

                <Divider sx={{ mb: 1.5 }} />

                <Typography variant="subtitle2" sx={{ mb: 1 }}>
                    Frame Timing Statistics
                </Typography>

                <TimingStatsTable data={completionData} />
            </DialogContent>
            <DialogActions>
                <Button
                    onClick={handleOpenInPlayback}
                    variant="outlined"
                    size="small"
                    startIcon={<PlayArrowIcon />}
                >
                    Open in Playback
                </Button>
                <Button onClick={handleClose} variant="contained" size="small">
                    Close
                </Button>
            </DialogActions>
        </Dialog>
    );
};
