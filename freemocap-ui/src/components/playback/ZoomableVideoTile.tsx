import React, {useCallback, useRef} from 'react';
import {useTranslation} from 'react-i18next';
import {useZoomTransform} from '@/hooks/useZoomTransform';
import type {PlaybackController} from './usePlaybackController';

interface ZoomableVideoTileProps {
    videoId: string;
    streamUrl: string;
    filename: string;
    showOverlays: boolean;
    hasError: boolean;
    setVideoRef: PlaybackController['setVideoRef'];
    setFrameOverlayRef: PlaybackController['setFrameOverlayRef'];
}

export const ZoomableVideoTile: React.FC<ZoomableVideoTileProps> = ({
    videoId,
    streamUrl,
    filename,
    showOverlays,
    hasError,
    setVideoRef,
    setFrameOverlayRef,
}) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const registerVideo = useCallback((element: HTMLVideoElement | null): void => {
        setVideoRef(videoId, element);
    }, [videoId, setVideoRef]);
    const { zoomWrapperStyle, cursor, containerHandlers } = useZoomTransform(containerRef);
    const { t } = useTranslation();

    return (
        <div
            ref={containerRef}
            className="w-full h-full overflow-hidden pos-rel"
            style={{
                backgroundColor: '#000',
                cursor,
            }}
            {...containerHandlers}
        >
            <div style={zoomWrapperStyle}>
                <video playsInline muted
                    ref={registerVideo}
                    className="w-full h-full block"
                    style={{ objectFit: 'contain' }}
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
                    <canvas width={210} height={18}
                        ref={(el) => setFrameOverlayRef(videoId, el)}
                        className="pos-abs top-6 right-6 z-10"
                        style={{
                            backgroundColor: 'rgba(0, 0, 0, 0.75)',
                            borderRadius: '3px',
                            userSelect: 'none', pointerEvents: 'none',
                        }}
                    />

                    <div title={filename} className="pos-abs bottom-6 left-6 z-10" style={{
                        maxWidth: 'calc(100% - 12px)', boxSizing: 'border-box',
                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                        backgroundColor: 'rgba(0, 0, 0, 0.75)',
                        color: '#ccc', padding: '2px 8px', borderRadius: '3px',
                        fontSize: '11px',
                        fontFamily: '"JetBrains Mono", "Fira Code", monospace',
                        userSelect: 'none',
                    }}>
                        {filename}
                    </div>

                </>
            )}
        </div>
    );
};

ZoomableVideoTile.displayName = 'ZoomableVideoTile';
