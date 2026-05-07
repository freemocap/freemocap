import React, {useRef} from 'react';
import {Box, Tooltip} from '@mui/material';
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

/**
 * Renders a single video tile with scroll-to-zoom, drag-to-pan,
 * and pinch-to-zoom. Can be used as a direct child of ReactGridLayout
 * because the root div has no ref — GridItem's cloneElement safely
 * adds its own ref for drag/resize without clobbering containerRef.
 * The inner div handles zoom coordinate calculations.
 */
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
                    {/* FRAME NUMBER */}
                    <Box
                        ref={(el: HTMLElement | null) => setFrameOverlayRef(videoId, el)}
                        sx={{
                            position: 'absolute', top: 6, right: 6,
                            backgroundColor: 'rgba(0, 0, 0, 0.88)',
                            color: '#00ff88',
                            px: 1.25, py: 0.4, borderRadius: '4px',
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
                    </Box>

                    {/* CAMERA ID */}
                    <Box sx={{
                        position: 'absolute', bottom: 6, left: 6,
                        backgroundColor: 'rgba(0, 0, 0, 0.75)',
                        color: '#ccc', px: 1, py: 0.25, borderRadius: '3px',
                        fontSize: '11px',
                        fontFamily: '"JetBrains Mono", "Fira Code", monospace',
                        userSelect: 'none', pointerEvents: 'none', zIndex: 10,
                    }}>
                        {filename}
                    </Box>

                    {/* TIMECODE */}
                    <Tooltip title={timestampsAreReal ? t("timestampFromRecording") : t("estimatedFromFrameNumber")} placement="top-end">
                        <Box
                            ref={(el: HTMLElement | null) => setTimeOverlayRef(videoId, el)}
                            sx={{
                                position: 'absolute', bottom: 6, right: 6,
                                backgroundColor: 'rgba(0, 0, 0, 0.75)',
                                color: '#aaa', px: 0.75, py: 0.25, borderRadius: '3px',
                                fontSize: '10px',
                                fontFamily: '"JetBrains Mono", "Fira Code", monospace',
                                userSelect: 'none', zIndex: 10,
                            }}
                        >
                            {initialTimeText}
                        </Box>
                    </Tooltip>
                </>
            )}
        </div>
    );
};

ZoomableVideoTile.displayName = 'ZoomableVideoTile';
