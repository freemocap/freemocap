import React, {useMemo} from 'react';
import ReactGridLayout, {noCompactor} from 'react-grid-layout';
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';
import {useTranslation} from 'react-i18next';
import type {PlaybackController} from './usePlaybackController';
import {ZoomableVideoTile} from './ZoomableVideoTile';
import {useGridLayout} from '@/hooks/useGridLayout';

interface VideoEntry {
    videoId: string;
    filename: string;
    streamUrl: string;
}

export interface PlaybackSettings {
    showOverlays: boolean;
    timestampFormat: 'timecode' | 'seconds';
}

interface SyncedVideoPlayerProps {
    videos: VideoEntry[];
    manualColumns: number | null;
    resetKey: number;
    controller: PlaybackController;
}

function formatTimecodeFromSeconds(seconds: number, fps: number): string {
    if (fps <= 0) return '00:00:00:00';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    const f = Math.floor((seconds % 1) * fps);
    const pad = (n: number) => n.toString().padStart(2, '0');
    return `${pad(h)}:${pad(m)}:${pad(s)}:${pad(f)}`;
}

function formatTimecode(frame: number, fps: number): string {
    if (fps <= 0) return '00:00:00:00';
    const totalSec = frame / fps;
    const h = Math.floor(totalSec / 3600);
    const m = Math.floor((totalSec % 3600) / 60);
    const s = Math.floor(totalSec % 60);
    const f = frame % Math.round(fps);
    const pad = (n: number) => n.toString().padStart(2, '0');
    return `${pad(h)}:${pad(m)}:${pad(s)}:${pad(f)}`;
}

function formatSeconds(frame: number, fps: number): string {
    if (fps <= 0) return '0.000s';
    return `${(frame / fps).toFixed(3)}s`;
}

export const SyncedVideoPlayer: React.FC<SyncedVideoPlayerProps> = ({
    videos,
    manualColumns,
    resetKey,
    controller,
}) => {
    const {t} = useTranslation();

    const {
        currentFrame,
        totalFrames,
        fps,
        settings,
        allReady,
        videosReady,
        erroredVideos,
        setVideoRef,
        setFrameOverlayRef,
        setTimeOverlayRef,
        handleLoadedMetadata,
        handleVideoError,
        frameTimestampsRef,
    } = controller;

    const videoIds = useMemo(() => videos.map(v => v.videoId), [videos]);

    const {
        containerRef,
        width,
        layout,
        gridHandlers,
        gridConfig,
    } = useGridLayout({
        itemIds: videoIds,
        margin: [2, 2],
        manualColumns,
        resetKey,
        measureParent: true,
    });

    if (videos.length === 0) {
        return (
            <div
                ref={containerRef}
                className="flex items-center justify-center h-full"
                style={{color: 'var(--color-text-secondary)'}}
            >
                <p className="text md text-gray">{t("noVideosLoaded")}</p>
            </div>
        );
    }

    const framePadLen = Math.max(String(totalFrames).length, 1);
    const initialFrameText = 'F' + String(currentFrame).padStart(framePadLen, '0');

    let initialTimeText: string;
    let timestampsAreReal = false;
    const frameTimestamps = frameTimestampsRef.current;
    if (frameTimestamps) {
        const firstKey = Object.keys(frameTimestamps)[0];
        const camTs = firstKey ? frameTimestamps[firstKey] : null;
        if (camTs && currentFrame < camTs.length) {
            const realSec = camTs[currentFrame];
            initialTimeText = settings.timestampFormat === 'timecode'
                ? formatTimecodeFromSeconds(realSec, fps)
                : `${realSec.toFixed(3)}s`;
            timestampsAreReal = true;
        } else {
            initialTimeText = '~' + (settings.timestampFormat === 'timecode'
                ? formatTimecode(currentFrame, fps)
                : formatSeconds(currentFrame, fps));
        }
    } else {
        initialTimeText = '~' + (settings.timestampFormat === 'timecode'
            ? formatTimecode(currentFrame, fps)
            : formatSeconds(currentFrame, fps));
    }

    return (
        <div
            ref={containerRef}
            className="pos-rel overflow-hidden w-full h-full"
            style={{backgroundColor: '#0a0a0a'}}
        >
            <ReactGridLayout
                width={width}
                layout={layout}
                gridConfig={gridConfig}
                dragConfig={{enabled: true}}
                resizeConfig={{enabled: true}}
                compactor={noCompactor}
                {...gridHandlers}
            >
                {videos.map((video) => (
                    <div
                        key={video.videoId}
                        className="overflow-hidden br-1"
                        style={{
                            border: '1px solid rgba(255,255,255,0.15)',
                        }}
                    >
                        <ZoomableVideoTile
                            videoId={video.videoId}
                            streamUrl={video.streamUrl}
                            filename={video.filename}
                            showOverlays={settings.showOverlays}
                            timestampFormat={settings.timestampFormat}
                            initialFrameText={initialFrameText}
                            initialTimeText={initialTimeText}
                            timestampsAreReal={timestampsAreReal}
                            hasError={erroredVideos.has(video.videoId)}
                            setVideoRef={setVideoRef}
                            setFrameOverlayRef={setFrameOverlayRef}
                            setTimeOverlayRef={setTimeOverlayRef}
                            handleLoadedMetadata={handleLoadedMetadata}
                            handleVideoError={handleVideoError}
                        />
                    </div>
                ))}
            </ReactGridLayout>

            {!allReady && videos.length > 0 && (
                <div className="pos-abs bottom-0 left-0 right-0 z-10 text-center" style={{
                    padding: '4px 0',
                    backgroundColor: 'var(--color-warning-dark)',
                    color: '#fff',
                }}>
                    <p className="text sm m-0">{t("loadingVideos", {ready: videosReady, total: videos.length})}</p>
                </div>
            )}
        </div>
    );
};
