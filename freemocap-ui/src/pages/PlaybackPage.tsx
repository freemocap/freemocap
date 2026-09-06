import ButtonSm from "@/components/ui-components/ButtonSm";
import {choosePlaybackBudget, DEFAULT_PLAYBACK_BYTES} from '@/services/recording/playback-budget';
import {fetchPlaybackBundle, selectPlaybackBundle} from '@/store/slices/playback-data/playback-data-slice';
import React, {useCallback, useEffect, useState} from 'react';
import {Footer} from '@/components/ui-components/Footer';
import ErrorBoundary from '@/components/common/ErrorBoundary';
import {SyncedVideoPlayer} from '@/components/playback/SyncedVideoPlayer';
import {PlaybackControls} from '@/components/playback/PlaybackControls';
import {usePlaybackController} from '@/components/playback/usePlaybackController';
import {usePlaybackContext} from '@/components/playback/PlaybackContext';
import {useElectronIPC} from '@/services';
import {useTranslation} from 'react-i18next';
import type {CameraSettings} from '@/pages/StreamingViewPage';
import {GridSettingsOverlay} from "@/components/ui-components/GridSettingsOverlay";
import IconButton from "@/components/ui-components/IconButton";
import {Panel, PanelGroup, PanelResizeHandle} from "react-resizable-panels";
import {ThreeJsCanvas} from "@/components/viewport3d/ThreeJsCanvas";
import {RecordingPlaybackProvider} from "@/components/viewport3d/RecordingPlaybackProvider";
import {useAppDispatch, useAppSelector} from "@/store";
import {
    selectActiveRecordingBaseDirectory,
    selectActiveRecordingFullPath,
    selectActiveRecordingName,
} from "@/store/slices/active-recording/active-recording-slice";

const PlaybackPage: React.FC = () => {
    const {t} = useTranslation();
    const {api} = useElectronIPC();
    const ctx = usePlaybackContext();
    const [cacheBudgetBytes, setCacheBudgetBytes] = useState<number | null>(null);
    const [memoryError, setMemoryError] = useState<Error | null>(null);
    useEffect(() => {
        let active = true;
        if (!api) {setCacheBudgetBytes(DEFAULT_PLAYBACK_BYTES); return;}
        void api.memoryInfo.query().then(memory => {
            if (active) setCacheBudgetBytes(choosePlaybackBudget(memory));
        }).catch(error => {if (active) setMemoryError(error instanceof Error ? error : new Error(String(error)));});
        return () => {active = false;};
    }, [api]);
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

    const [folderError, setFolderError] = useState<string | null>(null);
    const handleOpenFolder = useCallback(async (): Promise<void> => {
        setFolderError(null);
        try {
            if (!recordingPath || !api) throw new Error("Opening folders requires a selected recording in the desktop app");
            await api.fileSystem.openFolder.mutate({path: recordingPath});
        } catch (err) {
            setFolderError(err instanceof Error ? err.message : String(err));
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
        sizeBytes: v.sizeBytes,
    }));

    const dispatch = useAppDispatch();
    const bundle = useAppSelector(selectPlaybackBundle(activeRecordingName, activeRecordingBaseDirectory));
    const reloadManifest = useCallback((): void => {
        if (activeRecordingName) void dispatch(fetchPlaybackBundle({recordingId: activeRecordingName, recordingParentDirectory: activeRecordingBaseDirectory}));
    }, [dispatch, activeRecordingName, activeRecordingBaseDirectory]);
    const controller = usePlaybackController({
        bundle, reloadManifest, cacheBudgetBytes,
        videos: videoEntries,
        recordingId: activeRecordingName,
        recordingParentDirectory: activeRecordingBaseDirectory,
        onFrameChange,
    });

    if (memoryError) throw memoryError;
    return (
        <div className="playback-mode-main-container flex flex-col flex-1 pos-rel h-full">
            <GridSettingsOverlay
                settings={settings}
                onSettingsChange={handleSettingsChange}
            />

            <div className="flex flex-col flex-1 overflow-hidden">
                <ErrorBoundary>
                    <div className="flex flex-col pos-rel flex-1 min-h-0">
                        <div className="playback-mode-top-mid-bar flex flex-row items-center gap-1 flex-wrap  p-2">
                            <div className="flex flex-col min-w-0 flex-1 overflow-hidden">
                                <p className="text md m-0 truncate" title={recordingPath ?? undefined}>{recordingName}</p>
                                {recordingPath && <span className="recording-path-preview recording-path-tail text sm" title={recordingPath}>
                                    <bdi dir="ltr">{recordingPath}</bdi>
                                </span>}
                            </div>
                            <ButtonSm iconClass="subfolder-icon" buttonType="secondary"
                                text="Open recording folder" disabled={!recordingPath || !api}
                                title={recordingPath ?? 'Select a recording'}
                                onClick={() => void handleOpenFolder()}/>


                            <div className="flex-1"/>

                            <span title={t('cameraStreams')} className="tag text sm">
                                {t('cameraCount', {count: loadedVideos.length})}
                            </span>

                            {totalSize > 0 && (
                                <span title={t('totalRecordingSize')} className="tag text sm">
                                    {formatBytes(totalSize)}
                                </span>
                            )}

                            {recordingFps != null && recordingFps > 0 && (
                                <span title={t('recordingCaptureFps')} className="tag text sm">
                                    rec: {recordingFps} fps
                                </span>
                            )}
                        </div>

                        {folderError && <p role="alert" className="text-error">{folderError}</p>}
                        <div className="playback-mode-below-main p-1 flex flex-col flex-1 min-h-0">
                            {settings.show3dView ? (
                                <PanelGroup
                                    key={`main-panels-${resetKey}-${settings.layoutDirection}`}
                                    direction={settings.layoutDirection}
                                >
                                    <Panel defaultSize={60} minSize={20}>
                                        <div className="playback-mode-video-feed-container br-2 flex flex-col h-full">
                                            <SyncedVideoPlayer
                                                videos={videoEntries}
                                                manualColumns={settings.columns}
                                                resetKey={resetKey}
                                                controller={controller}
                                            />
                                        </div>
                                    </Panel>

                                     <PanelResizeHandle
                                               className="resizable-component"
                                               style={{
                                                 width: "4px",
                                                 cursor: "col-resize",
                                                 backgroundColor: "var(--color-surface-active)",
                                               }}
                                             />

                                    <Panel defaultSize={40} minSize={10}>
                                        <div className="h-full">
                                            <RecordingPlaybackProvider
                                                recordingId={activeRecordingName}
                                                recordingParentDirectory={activeRecordingBaseDirectory}
                                                getRecordingTime={controller.getRecordingTime}
                                                mediaAvailable={videoEntries.length > 0}
                                                manifest={controller.manifest}
                                                reloadManifest={controller.reloadManifest}
                                                onPlaybackRun={controller.setPlaybackRun}
                                            >
                                                <ThreeJsCanvas/>
                                            </RecordingPlaybackProvider>
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

                        {controller.error && <p role="alert" className="text-error">{controller.error}</p>}
                        <PlaybackControls
                            isPlaying={controller.isPlaying}
                            currentTime={controller.currentTime}
                            duration={controller.duration}
                            playbackRate={controller.playbackRate}
                            currentFrame={controller.currentFrame}
                            seekFrame={controller.seekFrame}
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

