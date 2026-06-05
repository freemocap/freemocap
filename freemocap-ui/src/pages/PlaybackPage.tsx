import React, {useCallback, useEffect, useState} from 'react';
import {Footer} from '@/components/ui-components/Footer';
import ErrorBoundary from '@/components/common/ErrorBoundary';
import {SyncedVideoPlayer} from '@/components/playback/SyncedVideoPlayer';
import {PlaybackControls} from '@/components/playback/PlaybackControls';
import {usePlaybackController} from '@/components/playback/usePlaybackController';
import {usePlaybackContext} from '@/components/playback/PlaybackContext';
import {useElectronIPC} from '@/services';
import {useTranslation} from 'react-i18next';
import {useNavigate} from 'react-router-dom';
import type {CameraSettings} from '@/pages/StreamingViewPage';
import {SettingsOverlay} from "@/components/ui-components/SettingsOverlay";
import {Panel, PanelGroup, PanelResizeHandle} from "react-resizable-panels";
import {ThreeJsCanvas} from "@/components/viewport3d/ThreeJsCanvas";
import {FileKeypointsSourceProvider} from "@/components/viewport3d/FileKeypointsSourceProvider";
import {useAppSelector} from "@/store";
import {
    selectActiveRecordingBaseDirectory,
    selectActiveRecordingFullPath,
    selectActiveRecordingName,
} from "@/store/slices/active-recording/active-recording-slice";

const PlaybackPage: React.FC = () => {
    const {t} = useTranslation();
    const {api} = useElectronIPC();
    const navigate = useNavigate();

    const ctx = usePlaybackContext();
    const activeRecordingPath = useAppSelector(selectActiveRecordingFullPath);
    const activeRecordingName = useAppSelector(selectActiveRecordingName);
    const activeRecordingBaseDirectory = useAppSelector(selectActiveRecordingBaseDirectory);

    const [settings, setSettings] = useState<CameraSettings>({
        columns: null,
        show3dView: true,
        layoutDirection: 'horizontal',
    });
    const [resetKey, setResetKey] = useState<number>(0);

    const isHorizontal = settings.layoutDirection === 'horizontal';

    const loadedVideos = ctx?.loadedVideos ?? [];
    const recordingPath = activeRecordingPath;
    const recordingFps = ctx?.recordingFps;
    const frameTimestamps = ctx?.frameTimestamps ?? null;
    const onFrameChange = ctx?.onFrameChange;
    const availableSources = ctx?.availableSources ?? null;
    const selectedSource = ctx?.selectedSource ?? null;
    const setSelectedSource = ctx?.setSelectedSource;

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

    const controller = usePlaybackController({
        videos: videoEntries,
        recordingFps,
        frameTimestamps,
        initialFrame: ctx?.cachedCurrentFrame ?? 0,
        onFrameChange,
    });

    return (
        <div className="flex flex-col flex-1 bg-dark" style={{height: '100%', border: '1px solid var(--color-border-secondary)'}}>
            <div className="flex flex-col flex-1 overflow-hidden">
                <ErrorBoundary>
                    <div className="flex flex-col pos-rel flex-1" style={{minHeight: 0}}>
                        <SettingsOverlay
                            settings={settings}
                            onSettingsChange={handleSettingsChange}
                            onResetLayout={handleResetLayout}
                        />

                        <div className="flex flex-row items-center gap-1" style={{
                            padding: '6px 12px',
                            borderBottom: '1px solid var(--color-border-secondary)',
                            backgroundColor: 'rgba(255,255,255,0.03)',
                            minHeight: 40,
                            flexWrap: 'wrap',
                        }}>
                            <p className="text md text-white text-nowrap" style={{fontFamily: monoFont, fontWeight: 600, margin: 0}}>
                                {recordingName}
                            </p>

                            <button
                                title="Browse recordings"
                                className="button icon-button br-1"
                                onClick={() => navigate('/browse')}
                                style={{border: '1px solid rgba(255,255,255,0.15)', borderRadius: '6px', padding: '0 8px', gap: 4, fontSize: '0.75rem', fontFamily: monoFont}}
                            >
                                <span className="icon load-icon icon-size-20"/>
                                Browse
                            </button>

                            <button
                                title={t('openFolder')}
                                className="button icon-button br-1"
                                onClick={handleOpenFolder}
                                style={{color: 'var(--color-warning)', border: '1px solid rgba(230,73,0,0.3)', borderRadius: '6px', padding: '0 8px'}}
                            >
                                <span className="icon load-icon icon-size-20"/>
                            </button>

                            <div style={{flex: 1}}/>

                            <span title={t('cameraStreams')} className="tag text sm" style={{fontFamily: monoFont, color: 'var(--color-info)', borderColor: 'rgba(43,164,255,0.3)'}}>
                                {t('cameraCount', {count: loadedVideos.length})}
                            </span>

                            {totalSize > 0 && (
                                <span title={t('totalRecordingSize')} className="tag text sm" style={{fontFamily: monoFont}}>
                                    {formatBytes(totalSize)}
                                </span>
                            )}

                            {recordingFps != null && recordingFps > 0 && (
                                <span title={t('recordingCaptureFps')} className="tag text sm" style={{fontFamily: monoFont, color: 'var(--color-warning)', borderColor: 'rgba(230,73,0,0.3)'}}>
                                    rec: {recordingFps} fps
                                </span>
                            )}
                        </div>

                        <div className="flex flex-col flex-1" style={{minHeight: 0}}>
                            {settings.show3dView ? (
                                <PanelGroup
                                    key={`main-panels-${resetKey}-${settings.layoutDirection}`}
                                    direction={settings.layoutDirection}
                                >
                                    <Panel defaultSize={60} minSize={20}>
                                        <div className="flex flex-col" style={{height: '100%'}}>
                                            <SyncedVideoPlayer
                                                videos={videoEntries}
                                                manualColumns={settings.columns}
                                                resetKey={resetKey}
                                                controller={controller}
                                            />
                                        </div>
                                    </Panel>

                                    <PanelResizeHandle>
                                        <div style={{
                                            display: 'flex',
                                            alignItems: 'center',
                                            justifyContent: 'center',
                                            backgroundColor: 'var(--color-border-secondary)',
                                            transition: 'background-color 0.15s ease',
                                            cursor: isHorizontal ? 'col-resize' : 'row-resize',
                                            ...(isHorizontal
                                                ? {width: '6px', height: '100%', flexDirection: 'column' as const}
                                                : {height: '6px', width: '100%', flexDirection: 'row' as const}
                                            ),
                                        }}>
                                            {[0, 1, 2].map((i) => (
                                                <div key={i} style={{
                                                    width: 4, height: 4, borderRadius: '50%',
                                                    backgroundColor: 'var(--color-text-disabled)',
                                                    margin: isHorizontal ? '2px 0' : '0 2px',
                                                    flexShrink: 0,
                                                }}/>
                                            ))}
                                        </div>
                                    </PanelResizeHandle>

                                    <Panel defaultSize={40} minSize={10}>
                                        <div style={{height: '100%'}}>
                                            <FileKeypointsSourceProvider
                                                recordingId={activeRecordingName}
                                                recordingParentDirectory={activeRecordingBaseDirectory}
                                                currentFrameRef={controller.currentFrameRef}
                                            >
                                                <ThreeJsCanvas/>
                                            </FileKeypointsSourceProvider>
                                        </div>
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
                        </div>

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
                            availableSources={availableSources}
                            selectedSource={selectedSource}
                            onSourceChange={setSelectedSource}
                        />
                    </div>
                </ErrorBoundary>
            </div>
        </div>
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
