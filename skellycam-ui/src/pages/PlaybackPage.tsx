import React, { useCallback, useState } from 'react';
import { Footer } from '@/components/ui-components/Footer';
import ErrorBoundary from '@/components/common/ErrorBoundary';
import { SyncedVideoPlayer } from '@/components/playback/SyncedVideoPlayer';
import { CamerasViewSettingsOverlay } from '@/components/camera-view-settings-overlay/CamerasViewSettingsOverlay';
import { useElectronIPC } from '@/services';
import { useTranslation } from 'react-i18next';
import IconButton from '@/components/ui-components/IconButton';
import { usePlaybackContext } from '@/contexts/PlaybackContext';

const PlaybackPage: React.FC = () => {
    const { t } = useTranslation();
    const { api } = useElectronIPC();

    const {
        loadedVideos,
        recordingPath,
        recordingFps,
        frameTimestamps,
        currentFrame,
        handleBack,
        handleFrameChange,
    } = usePlaybackContext();

    const [manualColumns, setManualColumns] = useState<number | null>(null);
    const [resetKey, setResetKey] = useState<number>(0);

    const handleOpenFolder = useCallback(async () => {
        if (!recordingPath) return;
        try {
            await api?.fileSystem.openFolder.mutate({ path: recordingPath });
        } catch (err) {
            console.error('Failed to open recording folder:', err);
            throw err;
        }
    }, [recordingPath, api]);

    const handleSettingsChange = useCallback((settings: { columns: number | null }) => {
        setManualColumns(settings.columns);
    }, []);

    const handleResetLayout = useCallback(() => {
        setResetKey((v) => v + 1);
    }, []);

    const hasVideos = loadedVideos.length > 0;
    const totalSize = loadedVideos.reduce((sum, v) => sum + v.sizeBytes, 0);

    const recordingName = recordingPath ? recordingPath.split(/[\\/]/).pop() || recordingPath : '';

    return (
        <div className="playback-page h-full flex flex-col">
            <div className='mode-header playback-mode w-full reveal fadeIn active-tools-header br-1-1 gap-1 p-1 flex justify-content-space-between'>

            </div><div className="playback-page-content-main flex flex-col flex-1 overflow-hidden p-2 bg-middark rounded mt-1 br-2">
                <ErrorBoundary>
                    {hasVideos ? (
                        <div className="playback-page-content no-videos empty-state flex flex-col h-full">
                            {/* Recording header bar */}
                            <div
                                className="playback-page-with-video flex items-center gap-2 px-2 py-1 flex-wrap m-1 ml-2"
                            >
                                <IconButton
                                    icon="back-icon"
                                    onClick={handleBack}
                                    tooltip={true}
                                    tooltipText='Back'
                                    tooltipPosition='pos-bottom'
                                />

                                <p className="text sm recording-name flex-1 overflow-hidden" style={{ textOverflow: 'ellipsis', whiteSpace: 'nowrap', minWidth: 0 }}>
                                    {recordingName}
                                </p>

                                <button
                                    className="button md"
                                    onClick={handleOpenFolder}
                                    title={t('openFolder')}
                                >
                                    <span className="icon import-icon icon-size-20" />
                                </button>

                                <span className="camera-config-chip" title={t('cameraStreams')}>
                                    {t('cameraCount', { count: loadedVideos.length })}
                                </span>

                                {totalSize > 0 && (
                                    <span className="camera-config-chip" title={t('totalRecordingSize')}>
                                        {formatBytes(totalSize)}
                                    </span>
                                )}

                                {recordingFps != null && recordingFps > 0 && (
                                    <span className="camera-config-chip" title={t('recordingCaptureFps')}>
                                        rec: {recordingFps} fps
                                    </span>
                                )}

                                <CamerasViewSettingsOverlay
                                    inline
                                    onSettingsChange={handleSettingsChange}
                                    onResetLayout={handleResetLayout}
                                />
                            </div>

                            {/* Player */}
                            <div className="flex-1" style={{ minHeight: 0 }}>
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
                                    initialFrame={currentFrame}
                                    onFrameChange={handleFrameChange}
                                />
                            </div>
                        </div>
                    ) : (
                        <div className="flex flex-col h-full items-center justify-center gap-2">
                            <span className="icon load-icon icon-size-32 text-muted" />
                            <p className="text md text-muted">{t('selectRecordingFromSidebar', 'Select a recording from the sidebar')}</p>
                        </div>
                    )}
                </ErrorBoundary>
            </div>

            <footer className="p-1">
                <Footer />
            </footer>
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
