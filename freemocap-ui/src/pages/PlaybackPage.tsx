import React, { useCallback, useEffect, useState } from 'react';
import { Box, Chip, IconButton, Tooltip, Typography, useTheme } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import VideocamIcon from '@mui/icons-material/Videocam';
import StorageIcon from '@mui/icons-material/Storage';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import { Footer } from '@/components/ui-components/Footer';
import ErrorBoundary from '@/components/common/ErrorBoundary';
import { RecordingBrowser, LoadedVideo } from '@/components/playback/RecordingBrowser';
import { SyncedVideoPlayer } from '@/components/playback/SyncedVideoPlayer';
import { CamerasViewSettingsOverlay } from '@/components/camera-view-settings-overlay/CamerasViewSettingsOverlay';
import { useElectronIPC } from '@/services';
import { serverUrls } from '@/services/server/server-helpers/server-urls';
import { useTranslation } from 'react-i18next';
import { useLocation } from 'react-router-dom';
import type { CameraSettings } from '@/pages/CamerasPage';

// Module-level cache so playback state survives tab switches
let cachedPlaybackState: {
    loadedVideos: LoadedVideo[];
    recordingPath: string | null;
    recordingFps: number | undefined;
    frameTimestamps: Record<string, number[]> | null;
    currentFrame: number;
} = {
    loadedVideos: [],
    recordingPath: null,
    recordingFps: undefined,
    frameTimestamps: null,
    currentFrame: 0,
};

const PlaybackPage: React.FC = () => {
    const theme = useTheme();
    const { t } = useTranslation();
    const { api } = useElectronIPC();
    const location = useLocation();
    const isDark = theme.palette.mode === 'dark';
    const locationState = location.state as { loadRecordingPath?: string } | null;
    const initialLoadPath = locationState?.loadRecordingPath ?? null;

    // If navigating here with a new recording path, clear cached state so RecordingBrowser shows and auto-loads
    const initState = (initialLoadPath && initialLoadPath !== cachedPlaybackState.recordingPath)
        ? { loadedVideos: [] as LoadedVideo[], recordingPath: null, recordingFps: undefined, frameTimestamps: null, currentFrame: 0 }
        : cachedPlaybackState;

    const [loadedVideos, setLoadedVideos] = useState<LoadedVideo[]>(initState.loadedVideos);
    const [recordingPath, setRecordingPath] = useState<string | null>(initState.recordingPath);
    const [recordingFps, setRecordingFps] = useState<number | undefined>(initState.recordingFps);
    const [frameTimestamps, setFrameTimestamps] = useState<Record<string, number[]> | null>(initState.frameTimestamps);
    const [manualColumns, setManualColumns] = useState<number | null>(null);
    const [resetKey, setResetKey] = useState<number>(0);

    const handleRecordingLoaded = useCallback((videos: LoadedVideo[], path: string, fps?: number) => {
        setLoadedVideos(videos);
        setRecordingPath(path);
        setRecordingFps(fps);
        setFrameTimestamps(null);
        cachedPlaybackState = { loadedVideos: videos, recordingPath: path, recordingFps: fps, frameTimestamps: null, currentFrame: 0 };
    }, []);

    // After a recording is loaded, fetch real timestamps from the server
    useEffect(() => {
        if (loadedVideos.length === 0) return;

        const fetchTimestamps = async () => {
            try {
                const response = await fetch(serverUrls.endpoints.playbackAllTimestamps);
                if (!response.ok) return;
                const data = await response.json();
                if (data.timestamps && Object.keys(data.timestamps).length > 0) {
                    setFrameTimestamps(data.timestamps);
                    cachedPlaybackState.frameTimestamps = data.timestamps;
                }
            } catch {
                // Timestamps not available — SyncedVideoPlayer will use approximation
            }
        };
        fetchTimestamps();
    }, [loadedVideos]);

    const handleBack = useCallback(() => {
        setLoadedVideos([]);
        setRecordingPath(null);
        setRecordingFps(undefined);
        setFrameTimestamps(null);
        cachedPlaybackState = { loadedVideos: [], recordingPath: null, recordingFps: undefined, frameTimestamps: null, currentFrame: 0 };
    }, []);

    const handleOpenFolder = useCallback(async () => {
        if (!recordingPath) return;
        try {
            await api?.fileSystem.openFolder.mutate({ path: recordingPath });
        } catch (err) {
            console.error('Failed to open recording folder:', err);
            throw err;
        }
    }, [recordingPath, api]);

    const handleSettingsChange = useCallback((partial: Partial<CameraSettings>) => {
        if (partial.columns !== undefined) {
            setManualColumns(partial.columns);
        }
    }, []);

    const handleResetLayout = useCallback(() => {
        setResetKey((v) => v + 1);
    }, []);

    const handleFrameChange = useCallback((frame: number) => {
        cachedPlaybackState.currentFrame = frame;
    }, []);

    const hasVideos = loadedVideos.length > 0;
    const totalSize = loadedVideos.reduce((sum, v) => sum + v.sizeBytes, 0);
    const monoFont = '"JetBrains Mono", "Fira Code", "SF Mono", monospace';

    // Extract recording name from path
    const recordingName = recordingPath ? recordingPath.split(/[\\/]/).pop() || recordingPath : '';

    return (
        <Box
            sx={{
                flex: 1,
                display: 'flex',
                flexDirection: 'column',
                height: '100%',
                backgroundColor: theme.palette.mode === 'dark'
                    ? theme.palette.background.default
                    : theme.palette.background.paper,
                borderStyle: 'solid',
                borderWidth: '1px',
                borderColor: theme.palette.divider,
            }}
        >
            <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
                <ErrorBoundary>
                    {hasVideos ? (
                        <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', position: 'relative' }}>
                            {/* Settings overlay for grid columns */}
                            <CamerasViewSettingsOverlay
                                settings={{ columns: manualColumns, show3dView: false, layoutDirection: 'horizontal' }}
                                onSettingsChange={handleSettingsChange}
                                onResetLayout={handleResetLayout}
                            />

                            {/* Recording header bar */}
                            <Box
                                sx={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: 1.5,
                                    px: 1.5,
                                    py: 0.75,
                                    borderBottom: `1px solid ${theme.palette.divider}`,
                                    backgroundColor: isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.02)',
                                    minHeight: 40,
                                    flexWrap: 'wrap',
                                }}
                            >
                                <Tooltip title={t('backToRecordings')}>
                                    <IconButton size="small" onClick={handleBack}
                                        sx={{ color: isDark ? '#b3b9c6' : undefined }}>
                                        <ArrowBackIcon fontSize="small" />
                                    </IconButton>
                                </Tooltip>

                                {/* Recording name */}
                                <Typography
                                    variant="body2"
                                    sx={{
                                        fontFamily: monoFont,
                                        fontWeight: 600,
                                        color: theme.palette.text.primary,
                                        overflow: 'hidden',
                                        textOverflow: 'ellipsis',
                                        whiteSpace: 'nowrap',
                                    }}
                                >
                                    {recordingName}
                                </Typography>

                                {/* Open Folder button */}
                                <Tooltip title={t('openFolder')}>
                                    <IconButton
                                        size="small"
                                        onClick={handleOpenFolder}
                                        sx={{
                                            color: isDark ? '#ffcc80' : theme.palette.warning.dark,
                                            border: `1px solid ${isDark ? 'rgba(255,204,128,0.3)' : theme.palette.warning.light}`,
                                            borderRadius: '6px',
                                            px: 1,
                                            gap: 0.5,
                                            fontSize: '0.75rem',
                                            fontFamily: monoFont,
                                            '&:hover': {
                                                backgroundColor: isDark ? 'rgba(255,204,128,0.1)' : 'rgba(255,152,0,0.08)',
                                            },
                                        }}
                                    >
                                        <FolderOpenIcon sx={{ fontSize: 16 }} />
                                    </IconButton>
                                </Tooltip>

                                {/* Spacer */}
                                <Box sx={{ flex: 1 }} />

                                {/* Stats chips */}
                                <Tooltip title={t('cameraStreams')}>
                                    <Chip
                                        icon={<VideocamIcon sx={{ fontSize: '14px !important' }} />}
                                        label={t('cameraCount', { count: loadedVideos.length })}
                                        size="small"
                                        variant="outlined"
                                        sx={{
                                            fontFamily: monoFont,
                                            fontSize: '0.75rem',
                                            height: 24,
                                            borderColor: isDark ? 'rgba(41,182,246,0.3)' : undefined,
                                            color: isDark ? '#29b6f6' : theme.palette.info.main,
                                            '& .MuiChip-icon': { color: 'inherit' },
                                        }}
                                    />
                                </Tooltip>

                                {totalSize > 0 && (
                                    <Tooltip title={t('totalRecordingSize')}>
                                        <Chip
                                            icon={<StorageIcon sx={{ fontSize: '14px !important' }} />}
                                            label={formatBytes(totalSize)}
                                            size="small"
                                            variant="outlined"
                                            sx={{
                                                fontFamily: monoFont,
                                                fontSize: '0.75rem',
                                                height: 24,
                                                borderColor: isDark ? 'rgba(255,255,255,0.15)' : undefined,
                                                color: isDark ? '#b3b9c6' : theme.palette.text.secondary,
                                                '& .MuiChip-icon': { color: 'inherit' },
                                            }}
                                        />
                                    </Tooltip>
                                )}

                                {recordingFps != null && recordingFps > 0 && (
                                    <Tooltip title={t('recordingCaptureFps')}>
                                        <Chip
                                            label={`rec: ${recordingFps} fps`}
                                            size="small"
                                            variant="outlined"
                                            sx={{
                                                fontFamily: monoFont,
                                                fontSize: '0.75rem',
                                                height: 24,
                                                borderColor: isDark ? 'rgba(255,204,128,0.3)' : undefined,
                                                color: isDark ? '#ffcc80' : theme.palette.warning.dark,
                                            }}
                                        />
                                    </Tooltip>
                                )}
                            </Box>

                            {/* Player */}
                            <Box sx={{ flex: 1, minHeight: 0 }}>
                                <SyncedVideoPlayer
                                    videos={loadedVideos.map((v) => ({
                                        videoId: v.videoId,
                                        filename: v.filename,
                                        streamUrl: v.streamUrl,
                                    }))}
                                    recordingFps={recordingFps}
                                    frameTimestamps={frameTimestamps}
                                    manualColumns={manualColumns}
                                    resetKey={resetKey}
                                    initialFrame={initState.currentFrame}
                                    onFrameChange={handleFrameChange}
                                />
                            </Box>
                        </Box>
                    ) : (
                        <RecordingBrowser onRecordingLoaded={handleRecordingLoaded} initialLoadPath={initialLoadPath} />
                    )}
                </ErrorBoundary>
            </Box>

            <Box component="footer" sx={{ p: 0.5 }}>
                <Footer />
            </Box>
        </Box>
    );
};

function formatBytes(bytes: number): string {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${(bytes / Math.pow(k, i)).toFixed(i > 1 ? 1 : 0)} ${units[i]}`;
}

export default PlaybackPage;
