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
    setVideoRef: PlaybackController['setVideoRef'];
    setFrameOverlayRef: PlaybackController['setFrameOverlayRef'];
    setTimeOverlayRef: PlaybackController['setTimeOverlayRef'];
    handleLoadedMetadata: PlaybackController['handleLoadedMetadata'];
}

export const ZoomableVideoTile: React.FC<ZoomableVideoTileProps> = ({
    videoId,
    streamUrl,
    filename,
    showOverlays,
    initialFrameText,
    initialTimeText,
    timestampsAreReal,
    setVideoRef,
    setFrameOverlayRef,
    setTimeOverlayRef,
    handleLoadedMetadata,
}) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const { zoomWrapperStyle, cursor, containerHandlers } = useZoomTransform(containerRef);
    const { t } = useTranslation();

    return (
        <div
            style={{
                width: '100%',
                height: '100%',
                overflow: 'hidden',
                backgroundColor: '#000',
                position: 'relative',
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
                    style={{ width: '100%', height: '100%', objectFit: 'contain', display: 'block' }}
                    onLoadedMetadata={handleLoadedMetadata}
                    onError={(e) => {
                        const v = e.currentTarget as HTMLVideoElement;
                        const err = v.error;
                        console.error(
                            `[playback] video error for ${videoId}: ` +
                            `code=${err?.code} message="${err?.message ?? 'unknown'}" src=${v.src}`
                        );
                    }}
                />
            </div>

            {showOverlays && (
                <>
                    <div
                        ref={(el: HTMLElement | null) => setFrameOverlayRef(videoId, el)}
                        style={{
                            position: 'absolute', top: 6, right: 6,
                            backgroundColor: 'rgba(0, 0, 0, 0.88)',
                            color: '#00ff88',
                            padding: '4px 10px', borderRadius: '4px',
                            fontSize: '14px', fontWeight: 700,
                            fontFamily: '"JetBrains Mono", "Fira Code", "SF Mono", "Cascadia Code", monospace',
                            letterSpacing: '0.5px', lineHeight: 1,
                            border: '1px solid rgba(0, 255, 136, 0.3)',
                            textShadow: '0 0 6px rgba(0, 255, 136, 0.4)',
                            minWidth: 60, textAlign: 'center',
                            userSelect: 'none', pointerEvents: 'none', zIndex: 10,
                        }}
                    >
                        {initialFrameText}
                    </div>

                    <div style={{
                        position: 'absolute', bottom: 6, left: 6,
                        backgroundColor: 'rgba(0, 0, 0, 0.75)',
                        color: '#ccc', padding: '2px 8px', borderRadius: '3px',
                        fontSize: '11px',
                        fontFamily: '"JetBrains Mono", "Fira Code", monospace',
                        userSelect: 'none', pointerEvents: 'none', zIndex: 10,
                    }}>
                        {filename}
                    </div>

                    <div
                        ref={(el: HTMLElement | null) => setTimeOverlayRef(videoId, el)}
                        title={timestampsAreReal ? t("timestampFromRecording") : t("estimatedFromFrameNumber")}
                        style={{
                            position: 'absolute', bottom: 6, right: 6,
                            backgroundColor: 'rgba(0, 0, 0, 0.75)',
                            color: '#aaa', padding: '2px 6px', borderRadius: '3px',
                            fontSize: '10px',
                            fontFamily: '"JetBrains Mono", "Fira Code", monospace',
                            userSelect: 'none', zIndex: 10,
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
