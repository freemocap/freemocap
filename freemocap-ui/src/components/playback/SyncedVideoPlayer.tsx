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

export const SyncedVideoPlayer: React.FC<SyncedVideoPlayerProps> = ({
    videos,
    manualColumns,
    resetKey,
    controller,
}) => {
    const {t} = useTranslation();

    const {
        settings,
        allReady,
        videosReady,
        erroredVideos,
        setVideoRef,
        setFrameOverlayRef,
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

    return (
        <div
            ref={containerRef}
            className="br-2 pos-rel overflow-hidden w-full h-full"
            
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
                        className="video-feed-tile overflow-hidden br-1"
                      
                    >
                        <ZoomableVideoTile
                            videoId={video.videoId}
                            streamUrl={video.streamUrl}
                            filename={video.filename}
                            showOverlays={settings.showOverlays}
                            hasError={erroredVideos.has(video.videoId)}
                            setVideoRef={setVideoRef}
                            setFrameOverlayRef={setFrameOverlayRef}
                        />
                    </div>
                ))}
            </ReactGridLayout>

            {!allReady && videos.length > 0 && (
                <div className="pos-abs bottom-0 left-0 right-0 z-10 text-center">
                    <p className="text sm m-0">{t("loadingVideos", {ready: videosReady, total: videos.length})}</p>
                </div>
            )}
        </div>
    );
};
