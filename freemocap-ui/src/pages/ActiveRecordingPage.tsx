import React, {useCallback} from 'react';
import {Box, Button, Chip, Stack, Tooltip, Typography, useTheme} from '@mui/material';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import VideoLibraryIcon from '@mui/icons-material/VideoLibrary';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import {useNavigate} from 'react-router-dom';
import {Footer} from '@/components/ui-components/Footer';
import ErrorBoundary from '@/components/common/ErrorBoundary';
import {RecordingStatusPanel} from '@/components/common/RecordingStatusPanel';
import {useRecordingStatus} from '@/hooks/useRecordingStatus';
import {useAppSelector} from '@/store';
import {
    selectActiveRecordingBaseDirectory,
    selectActiveRecordingFullPath,
    selectActiveRecordingName,
    selectActiveRecordingOrigin,
    selectActiveRecordingStructure,
} from '@/store/slices/active-recording/active-recording-slice';
import {useElectronIPC} from '@/services';
import {useTranslation} from 'react-i18next';
import {useBlender} from "@/hooks/useBlender";
import LaunchIcon from "@mui/icons-material/Launch";
import {RecordingInfoPanel} from '@/components/control-panels/recording-info-panel/RecordingInfoPanel';
import {CalibrationPanel} from '@/components/control-panels/calibration-control-panel/CalibrationPanel';
import {MocapPanel} from '@/components/control-panels/mocap-control-panel/MocapPanel';

const MONO_FONT = '"JetBrains Mono", "Fira Code", "SF Mono", monospace';

const ORIGIN_LABEL: Record<string, string> = {
    'pending-capture': 'Pending capture',
    'just-captured': 'Just captured',
    'browsed': 'Browsed',
    'auto-latest': 'Auto-loaded',
};

const ActiveRecordingPage: React.FC = () => {
    const theme = useTheme();
    const {t} = useTranslation();
    const navigate = useNavigate();
    const {api} = useElectronIPC();

    const {triggerOpenInBlender} = useBlender();

    const isDark = theme.palette.mode === 'dark';

    const recordingName = useAppSelector(selectActiveRecordingName);
    const baseDirectory = useAppSelector(selectActiveRecordingBaseDirectory);
    const fullPath = useAppSelector(selectActiveRecordingFullPath);
    const origin = useAppSelector(selectActiveRecordingOrigin);
    const structure = useAppSelector(selectActiveRecordingStructure);
    const {
        status,
        isLoading: statusLoading,
        error: statusError,
        refresh: refreshStatus,
    } = useRecordingStatus(recordingName, {
        autoFetch: !!recordingName,
        recordingParentDirectory: baseDirectory,
    });

    const handleOpenFolder = useCallback(async () => {
        if (!fullPath) return;
        try {
            await api?.fileSystem.openFolder.mutate({path: fullPath});
        } catch (err) {
            console.error('Failed to open recording folder:', err);
        }
    }, [fullPath, api]);

    const handleOpenInBlender = useCallback(async () => {
        if (!fullPath) return;
        void triggerOpenInBlender(fullPath);
    }, [structure?.blendPath, triggerOpenInBlender]);



    const pageBg = theme.palette.mode === 'dark'
        ? theme.palette.background.default
        : theme.palette.background.paper;

    return (
        <Box
            sx={{
                width: '100%',
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                overflowY: 'auto',
                overflowX: 'hidden',
                backgroundColor: pageBg,
                borderStyle: 'solid',
                borderWidth: '1px',
                borderColor: theme.palette.divider,
            }}
        >
            <Box sx={{display: 'flex', flexDirection: 'column', p: 2, gap: 2}}>
                <ErrorBoundary>
                    {!recordingName ? (
                        <Box sx={{py: 4, px: 2}}>
                            <Stack spacing={2} alignItems="flex-start">
                                <Typography variant="body2" color="text.disabled" sx={{fontStyle: 'italic'}}>
                                    No active recording. This folder will be created when you start recording.
                                </Typography>
                                <Stack direction="row" spacing={1} sx={{mt: 1}}>
                                    <Button variant="outlined" onClick={() => navigate('/streaming')}>
                                        Go to Streaming
                                    </Button>
                                    <Button variant="outlined" onClick={() => navigate('/browse')}>
                                        Browse recordings
                                    </Button>
                                </Stack>
                            </Stack>
                            <RecordingInfoPanel/>
                        </Box>
                    ) : (
                        <>
                            {/* Identity header */}
                            <Box
                                sx={{
                                    p: 2,
                                    borderRadius: 1,
                                    border: `1px solid ${theme.palette.divider}`,
                                    backgroundColor: isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.02)',
                                }}
                            >
                                <Stack direction="row" alignItems="center" spacing={1} sx={{mb: 1, flexWrap: 'wrap'}}>
                                    <Typography
                                        variant="h6"
                                        sx={{fontFamily: MONO_FONT, fontWeight: 600}}
                                    >
                                        {recordingName}
                                    </Typography>
                                    {origin && (
                                        <Chip
                                            label={ORIGIN_LABEL[origin] ?? origin}
                                            size="small"
                                            variant="outlined"
                                            sx={{height: 20, fontSize: '0.7rem'}}
                                        />
                                    )}
                                </Stack>
                                <Tooltip title={fullPath ?? ''}>
                                    <Typography
                                        variant="body2"
                                        sx={{
                                            fontFamily: MONO_FONT,
                                            color: theme.palette.text.secondary,
                                            overflow: 'hidden',
                                            textOverflow: 'ellipsis',
                                            whiteSpace: 'nowrap',
                                        }}
                                    >
                                        {fullPath}
                                    </Typography>
                                </Tooltip>
                                <Stack direction="row" spacing={1} sx={{mt: 2, flexWrap: 'wrap'}}>
                                    <Button
                                        size="small"
                                        variant="outlined"
                                        startIcon={<FolderOpenIcon/>}
                                        onClick={handleOpenFolder}
                                    >
                                        {t('openFolder')}
                                    </Button>
                                    <Button
                                        size="small"
                                        variant="outlined"
                                        startIcon={<PlayArrowIcon/>}
                                        onClick={() => navigate('/playback')}
                                    >
                                        Open in Playback
                                    </Button>
                                    <Button
                                        size="small"
                                        variant="outlined"
                                        startIcon={<LaunchIcon/>}
                                        onClick={handleOpenInBlender}
                                    >
                                        Open in Blender
                                    </Button>
                                    <Button
                                        size="small"
                                        variant="outlined"
                                        startIcon={<VideoLibraryIcon/>}
                                        onClick={() => navigate('/browse')}
                                    >
                                        Browse recordings
                                    </Button>
                                </Stack>
                            </Box>

                            {/* Derived-path summary */}
                            {structure && (
                                <Box
                                    sx={{
                                        p: 2,
                                        borderRadius: 1,
                                        border: `1px solid ${theme.palette.divider}`,
                                    }}
                                >
                                    <Typography variant="subtitle2" sx={{mb: 1}}>Canonical layout</Typography>
                                    <Stack spacing={0.5}>
                                        <PathRow label="videos/synchronized" value={structure.videosSynchronizedDir}/>
                                        <PathRow label="videos/annotated" value={structure.videosAnnotatedDir}/>
                                        <PathRow label="output/" value={structure.outputDir}/>
                                        <PathRow label="calibration.toml" value={structure.calibrationTomlPath}/>
                                        <PathRow label="recording_info.json" value={structure.recordingInfoPath}/>
                                        <PathRow label="data.parquet" value={structure.dataParquetPath}/>
                                        <PathRow label=".blend" value={structure.blendPath}/>
                                    </Stack>
                                </Box>
                            )}

                            {/* Stage checklist */}
                            <Box
                                sx={{
                                    p: 2,
                                    borderRadius: 1,
                                    border: `1px solid ${theme.palette.divider}`,
                                }}
                            >
                                <Typography variant="subtitle2" sx={{mb: 1}}>Pipeline stages</Typography>
                                <RecordingStatusPanel
                                    status={status}
                                    isLoading={statusLoading}
                                    error={statusError}
                                    onRefresh={refreshStatus}
                                    defaultExpanded
                                    recordingFolderPath={fullPath}
                                />
                            </Box>

                            {/* Control panels */}
                            <CalibrationPanel/>
                            <MocapPanel/>
                        </>
                    )}
                </ErrorBoundary>
            </Box>
            <Box component="footer" sx={{p: 0.5}}>
                <Footer/>
            </Box>
        </Box>
    );
};

const PathRow: React.FC<{ label: string; value: string }> = ({label, value}) => (
    <Stack direction="row" spacing={1} sx={{alignItems: 'center'}}>
        <Typography variant="caption" sx={{minWidth: 160, color: 'text.secondary'}}>{label}</Typography>
        <Typography
            variant="caption"
            sx={{
                fontFamily: MONO_FONT,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
            }}
        >
            {value}
        </Typography>
    </Stack>
);

export default ActiveRecordingPage;
