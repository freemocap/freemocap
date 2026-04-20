import React, {useCallback, useEffect, useState} from 'react';
import {Box, Chip, IconButton, Tooltip, Typography, useTheme} from '@mui/material';
import VideocamIcon from '@mui/icons-material/Videocam';
import StorageIcon from '@mui/icons-material/Storage';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import VideoLibraryIcon from '@mui/icons-material/VideoLibrary';
import {Footer} from '@/components/ui-components/Footer';
import ErrorBoundary from '@/components/common/ErrorBoundary';
import {SyncedVideoPlayer} from '@/components/playback/SyncedVideoPlayer';
import {PlaybackControls} from '@/components/playback/PlaybackControls';
import {usePlaybackController} from '@/components/playback/usePlaybackController';
import {usePlaybackContext} from '@/components/playback/PlaybackContext';
import {useElectronIPC} from '@/services';
import {useTranslation} from 'react-i18next';
import {useLocation, useNavigate} from 'react-router-dom';
import type {CameraSettings} from '@/pages/StreamingViewPage';
import {SettingsOverlay} from "@/components/ui-components/SettingsOverlay";
import {Panel, PanelGroup, PanelResizeHandle} from "react-resizable-panels";
import {ThreeJsCanvas} from "@/components/viewport3d/ThreeJsCanvas";
import {FileKeypointsSourceProvider} from "@/components/viewport3d/FileKeypointsSourceProvider";

const PlaybackPage: React.FC = () => {
    const theme = useTheme();
    const {t} = useTranslation();
    const {api} = useElectronIPC();
    const location = useLocation();
    const navigate = useNavigate();
    const isDark = theme.palette.mode === 'dark';
    const locationState = location.state as { loadRecordingPath?: string } | null;

    const ctx = usePlaybackContext();

    // Pass initialLoadPath from route state to the context
    useEffect(() => {
        const path = locationState?.loadRecordingPath ?? null;
        if (path) ctx?.setInitialLoadPath(path);
    }, [locationState?.loadRecordingPath]);

    const [settings, setSettings] = useState<CameraSettings>({
        columns: null,
        show3dView: true,
        layoutDirection: 'horizontal',
    });
    const [resetKey, setResetKey] = useState<number>(0);

    const isHorizontal = settings.layoutDirection === 'horizontal';

    const loadedVideos = ctx?.loadedVideos ?? [];
    const recordingPath = ctx?.recordingPath ?? null;
    const recordingFps = ctx?.recordingFps;
    const frameTimestamps = ctx?.frameTimestamps ?? null;
    const onFrameChange = ctx?.onFrameChange;

    const handleOpenFolder = useCallback(async () => {
        if (!recordingPath) return;
        try {
            await api?.fileSystem.openFolder.mutate({path: recordingPath});
        } catch (err) {
            console.error('Failed to open recording folder:', err);
        }
    }, [recordingPath, api]);

    const handleSettingsChange = useCallback((partial: Partial<CameraSettings>) => {
        setSettings((prev) => ({...prev, ...partial}));
    }, []);

    const handleResetLayout = useCallback(() => {
        setResetKey((v) => v + 1);
    }, []);

    const totalSize = loadedVideos.reduce((sum, v) => sum + v.sizeBytes, 0);
    const monoFont = '"JetBrains Mono", "Fira Code", "SF Mono", monospace';
    const recordingName = recordingPath ? recordingPath.split(/[\\/]/).pop() || recordingPath : t('noVideosLoaded');

    const videoEntries = loadedVideos.map((v) => ({
        videoId: v.videoId,
        filename: v.filename,
        streamUrl: v.streamUrl,
    }));

    // Playback controller — owns all playback state/logic
    const controller = usePlaybackController({
        videos: videoEntries,
        recordingFps,
        frameTimestamps,
        initialFrame: ctx?.cachedCurrentFrame ?? 0,
        onFrameChange,
    });

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
            <Box sx={{flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden'}}>
                <ErrorBoundary>
                    <Box sx={{display: 'flex', flexDirection: 'column', height: '100%', position: 'relative'}}>
                        {/* Settings overlay for grid columns */}
                        <SettingsOverlay
                            settings={settings}
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

                            {/* Browse Recordings button — navigates to the Browse tab */}
                            <Tooltip title="Browse recordings">
                                <IconButton
                                    size="small"
                                    onClick={() => navigate('/browse')}
                                    sx={{
                                        color: isDark ? '#b3b9c6' : theme.palette.text.secondary,
                                        border: `1px solid ${isDark ? 'rgba(255,255,255,0.15)' : theme.palette.divider}`,
                                        borderRadius: '6px',
                                        px: 1,
                                        gap: 0.5,
                                        fontSize: '0.75rem',
                                        fontFamily: monoFont,
                                        '&:hover': {
                                            backgroundColor: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.04)',
                                        },
                                    }}
                                >
                                    <VideoLibraryIcon sx={{fontSize: 16}}/>
                                    Browse
                                </IconButton>
                            </Tooltip>

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
                                    <FolderOpenIcon sx={{fontSize: 16}}/>
                                </IconButton>
                            </Tooltip>

                            {/* Spacer */}
                            <Box sx={{flex: 1}}/>

                            {/* Stats chips */}
                            <Tooltip title={t('cameraStreams')}>
                                <Chip
                                    icon={<VideocamIcon sx={{fontSize: '14px !important'}}/>}
                                    label={t('cameraCount', {count: loadedVideos.length})}
                                    size="small"
                                    variant="outlined"
                                    sx={{
                                        fontFamily: monoFont,
                                        fontSize: '0.75rem',
                                        height: 24,
                                        borderColor: isDark ? 'rgba(41,182,246,0.3)' : undefined,
                                        color: isDark ? '#29b6f6' : theme.palette.info.main,
                                        '& .MuiChip-icon': {color: 'inherit'},
                                    }}
                                />
                            </Tooltip>

                            {totalSize > 0 && (
                                <Tooltip title={t('totalRecordingSize')}>
                                    <Chip
                                        icon={<StorageIcon sx={{fontSize: '14px !important'}}/>}
                                        label={formatBytes(totalSize)}
                                        size="small"
                                        variant="outlined"
                                        sx={{
                                            fontFamily: monoFont,
                                            fontSize: '0.75rem',
                                            height: 24,
                                            borderColor: isDark ? 'rgba(255,255,255,0.15)' : undefined,
                                            color: isDark ? '#b3b9c6' : theme.palette.text.secondary,
                                            '& .MuiChip-icon': {color: 'inherit'},
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

                        {/* Video + 3D viewport area */}
                        <Box sx={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
                            {settings.show3dView ? (
                                <PanelGroup
                                    key={`main-panels-${resetKey}-${settings.layoutDirection}`}
                                    direction={settings.layoutDirection}
                                >
                                    <Panel defaultSize={60} minSize={20}>
                                        <Box sx={{height: '100%', display: 'flex', flexDirection: 'column'}}>
                                            <SyncedVideoPlayer
                                                videos={videoEntries}
                                                manualColumns={settings.columns}
                                                resetKey={resetKey}
                                                controller={controller}
                                            />
                                        </Box>
                                    </Panel>

                                    <PanelResizeHandle>
                                        <Box
                                            sx={{
                                                display: 'flex',
                                                alignItems: 'center',
                                                justifyContent: 'center',
                                                backgroundColor: theme.palette.divider,
                                                transition: 'background-color 0.15s ease',
                                                cursor: isHorizontal ? 'col-resize' : 'row-resize',
                                                ...(isHorizontal
                                                    ? {width: '6px', height: '100%', flexDirection: 'column'}
                                                    : {height: '6px', width: '100%', flexDirection: 'row'}
                                                ),
                                                '&:hover': {
                                                    backgroundColor: theme.palette.primary.main,
                                                },
                                                '&:active': {
                                                    backgroundColor: theme.palette.primary.dark,
                                                },
                                            }}
                                        >
                                            {[0, 1, 2].map((i) => (
                                                <Box
                                                    key={i}
                                                    sx={{
                                                        width: 4,
                                                        height: 4,
                                                        borderRadius: '50%',
                                                        backgroundColor: theme.palette.text.disabled,
                                                        m: isHorizontal ? '2px 0' : '0 2px',
                                                        flexShrink: 0,
                                                    }}
                                                />
                                            ))}
                                        </Box>
                                    </PanelResizeHandle>

                                    <Panel defaultSize={40} minSize={10}>
                                        <Box sx={{height: '100%'}}>
                                            <FileKeypointsSourceProvider
                                                recordingId={recordingPath}
                                                currentFrameRef={controller.currentFrameRef}
                                            >
                                                <ThreeJsCanvas/>
                                            </FileKeypointsSourceProvider>
                                        </Box>
                                    </Panel>
                                </PanelGroup>
                            ) : (
                                <SyncedVideoPlayer
                                    videos={videoEntries}
                                    manualColumns={settings.columns}
                                    resetKey={resetKey}
                                    controller={controller}
                                />
                            )}
                        </Box>
                        
                        {/* Playback controls — full width below video + 3D area */}
                        <PlaybackControls
                            isPlaying={controller.isPlaying}
                            currentTime={controller.currentTime}
                            duration={controller.duration}
                            playbackRate={controller.playbackRate}
                            currentFrame={controller.currentFrame}
                            totalFrames={controller.totalFrames}
                            fps={controller.fps}
                            recordingFps={recordingFps}
                            settings={controller.settings}
                            onSettingsChange={controller.setSettings}
                            onPlayPause={controller.handlePlayPause}
                            onSeekDrag={controller.handleSeekDrag}
                            onSeekCommit={controller.handleSeekCommit}
                            onFrameStep={controller.handleFrameStep}
                            onPlaybackRateChange={controller.handlePlaybackRateChange}
                            onSeekToStart={controller.handleSeekToStart}
                            onSeekToEnd={controller.handleSeekToEnd}
                            isLooping={controller.isLooping}
                            onToggleLoop={controller.handleToggleLoop}
                        />
                    </Box>
                </ErrorBoundary>
            </Box>

            <Box component="footer" sx={{p: 0.5}}>
                <Footer/>
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
