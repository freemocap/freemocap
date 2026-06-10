import React, {useRef} from 'react';
import {useTranslation} from 'react-i18next';
import {useZoomTransform} from '@/hooks/useZoomTransform';
import type {PlaybackController} from './usePlaybackController';

interface ZoomableVideoTileProps {
    videoId: string;
    streamUrl: string;
    filename: string;
    showOverlays: boolean;
    timestampFormat: 'timecode' | 'seconds';
    initialFrameText: string;
    initialTimeText: string;
    timestampsAreReal: boolean;
    hasError: boolean;
    setVideoRef: PlaybackController['setVideoRef'];
    setFrameOverlayRef: PlaybackController['setFrameOverlayRef'];
    setTimeOverlayRef: PlaybackController['setTimeOverlayRef'];
    handleLoadedMetadata: PlaybackController['handleLoadedMetadata'];
    handleVideoError: PlaybackController['handleVideoError'];
}

export const ZoomableVideoTile: React.FC<ZoomableVideoTileProps> = ({
    videoId,
    streamUrl,
    filename,
    showOverlays,
    initialFrameText,
    initialTimeText,
    timestampsAreReal,
    hasError,
    setVideoRef,
    setFrameOverlayRef,
    setTimeOverlayRef,
    handleLoadedMetadata,
    handleVideoError,
}) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const { zoomWrapperStyle, cursor, containerHandlers } = useZoomTransform(containerRef);
    const { t } = useTranslation();

    return (
        <div
            className="w-full h-full overflow-hidden pos-rel"
            style={{
                backgroundColor: '#000',
                cursor,
            }}
            {...containerHandlers}
        >
            <div ref={containerRef} style={zoomWrapperStyle}>
                <video
                    ref={(el) => setVideoRef(videoId, el)}
                    src={streamUrl}
                    preload="auto"
                    muted
                    playsInline
                    className="w-full h-full block"
                    style={{ objectFit: 'contain' }}
                    onLoadedMetadata={handleLoadedMetadata}
                    onError={(e) => {
                        const v = e.currentTarget as HTMLVideoElement;
                        const err = v.error;
                        console.error(
                            `[playback] video error for ${videoId}: ` +
                            `code=${err?.code} message="${err?.message ?? 'unknown'}" src=${v.src}`
                        );
                        handleVideoError(videoId);
                    }}
                />
            </div>

            {hasError && (
                <div className="pos-abs inset-0 flex flex-col items-center justify-center gap-1 p-4 text-center z-5" style={{
                    backgroundColor: 'rgba(0, 0, 0, 0.85)',
                    color: 'var(--color-error, #ff6b6b)',
                }}>
                    <span className="text sm" style={{fontWeight: 600}}>{t("videoPlaybackError")}</span>
                    <span className="text xs" style={{color: '#aaa', wordBreak: 'break-all'}}>{filename}</span>
                </div>
            )}

            {showOverlays && (
                <>
                    <div
                        ref={(el: HTMLElement | null) => setFrameOverlayRef(videoId, el)}
                        className="pos-abs top-6 right-6 z-10 text-center"
                        style={{
                            backgroundColor: 'rgba(0, 0, 0, 0.88)',
                            color: '#00ff88',
                            padding: '4px 10px', borderRadius: '4px',
                            fontSize: '14px', fontWeight: 700,
                            fontFamily: '"JetBrains Mono", "Fira Code", "SF Mono", "Cascadia Code", monospace',
                            letterSpacing: '0.5px', lineHeight: 1,
                            border: '1px solid rgba(0, 255, 136, 0.3)',
                            textShadow: '0 0 6px rgba(0, 255, 136, 0.4)',
                            minWidth: 60,
                            userSelect: 'none', pointerEvents: 'none',
                        }}
                    >
                        {initialFrameText}
                    </div>

                    <div className="pos-abs bottom-6 left-6 z-10" style={{
                        backgroundColor: 'rgba(0, 0, 0, 0.75)',
                        color: '#ccc', padding: '2px 8px', borderRadius: '3px',
                        fontSize: '11px',
                        fontFamily: '"JetBrains Mono", "Fira Code", monospace',
                        userSelect: 'none', pointerEvents: 'none',
                    }}>
                        {filename}
                    </div>

                    <div
                        ref={(el: HTMLElement | null) => setTimeOverlayRef(videoId, el)}
                        title={timestampsAreReal ? t("timestampFromRecording") : t("estimatedFromFrameNumber")}
                        className="pos-abs bottom-6 right-6 z-10"
                        style={{
                            backgroundColor: 'rgba(0, 0, 0, 0.75)',
                            color: '#aaa', padding: '2px 6px', borderRadius: '3px',
                            fontSize: '10px',
                            fontFamily: '"JetBrains Mono", "Fira Code", monospace',
                            userSelect: 'none',
                        }}
                    >
                        {initialTimeText}
                    </div>
                </>
            )}
        </div>
    );
};

ZoomableVideoTile.displayName = 'ZoomableVideoTile';
