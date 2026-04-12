import React, {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {Box, Tooltip, Typography, useTheme} from '@mui/material';
import type {Layout, LayoutItem} from 'react-grid-layout';
import ReactGridLayout, {noCompactor} from 'react-grid-layout';
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';
import {useTranslation} from 'react-i18next';
import type {PlaybackController} from './usePlaybackController';

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
    /** null = auto-optimize, number = manual column count */
    manualColumns: number | null;
    /** Increment to force layout reset */
    resetKey: number;
    /** Playback controller from usePlaybackController */
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

/**
 * Pure video grid renderer. All playback state is managed externally
 * via the PlaybackController from usePlaybackController.
 */
export const SyncedVideoPlayer: React.FC<SyncedVideoPlayerProps> = ({
    videos,
    manualColumns,
    resetKey,
    controller,
}) => {
    const theme = useTheme();
    const {t} = useTranslation();

    const {
        currentFrame,
        totalFrames,
        fps,
        settings,
        allReady,
        videosReady,
        setVideoRef,
        setFrameOverlayRef,
        setTimeOverlayRef,
        handleLoadedMetadata,
        settingsRef,
        frameTimestampsRef,
        fpsRef,
    } = controller;

    // -----------------------------------------------------------------------
    // Grid layout
    // -----------------------------------------------------------------------
    const GRID_COLS = 12;
    const GRID_MARGIN: [number, number] = [2, 2];

    const gridContainerRef = useRef<HTMLDivElement>(null);
    const [gridWidth, setGridWidth] = useState<number>(800);
    const [gridHeight, setGridHeight] = useState<number>(400);

    useEffect(() => {
        const el = gridContainerRef.current;
        if (!el) return;
        const measure = () => {
            const rect = el.getBoundingClientRect();
            setGridWidth(rect.width);
            setGridHeight(rect.height);
        };
        measure();
        const observer = new ResizeObserver(() => measure());
        observer.observe(el);
        return () => observer.disconnect();
    }, []);

    const computeTiling = (n: number, w: number, h: number) => {
        if (n <= 1) return {cols: 1, rows: 1};
        let bestCols = 1;
        let bestArea = 0;
        const TARGET_AR = 16 / 9; // Assume standard video aspect ratio
        for (let cols = 1; cols <= n; cols++) {
            const rows = Math.ceil(n / cols);
            const cellW = (w - GRID_MARGIN[0] * (cols - 1)) / cols;
            const cellH = (h - GRID_MARGIN[1] * (rows - 1)) / rows;
            if (cellW < 80 || cellH < 60) continue;
            
            // Calculate actual media fitted area preserving aspect ratio
            const fittedW = Math.min(cellW, cellH * TARGET_AR);
            const fittedH = fittedW / TARGET_AR;
            const area = n * fittedW * fittedH;
            
            if (area > bestArea) { bestArea = area; bestCols = cols; }
        }
        return {cols: bestCols, rows: Math.ceil(n / bestCols)};
    };

    const prevTilingRef = useRef({cols: 1, rows: 1});
    const tiling = useMemo(() => {
        const candidate = manualColumns !== null
            ? {cols: Math.max(1, Math.min(manualColumns, videos.length || 1)), rows: Math.ceil((videos.length || 1) / Math.max(1, Math.min(manualColumns, videos.length || 1)))}
            : computeTiling(videos.length, gridWidth, gridHeight);
        const prev = prevTilingRef.current;
        if (candidate.cols === prev.cols && candidate.rows === prev.rows) return prev;
        prevTilingRef.current = candidate;
        return candidate;
    }, [videos.length, gridWidth, gridHeight, manualColumns]);

    const buildVideoLayout = (vids: VideoEntry[]): LayoutItem[] => {
        if (vids.length === 0) return [];
        const colSpan = Math.floor(GRID_COLS / tiling.cols);
        return vids.map((v, i) => ({
            i: v.videoId,
            x: (i % tiling.cols) * colSpan,
            y: Math.floor(i / tiling.cols),
            w: colSpan,
            h: 1,
            minW: 1,
            minH: 1,
        }));
    };

    const [gridLayout, setGridLayout] = useState<LayoutItem[]>(() => buildVideoLayout(videos));

    useEffect(() => {
        setGridLayout(buildVideoLayout(videos));
    }, [videos, tiling, resetKey]);

    const gridLayoutBeforeDragRef = useRef<LayoutItem[]>(gridLayout);

    const handleGridDragStart = useCallback(() => {
        gridLayoutBeforeDragRef.current = gridLayout;
    }, [gridLayout]);

    const handleGridDragStop = useCallback((_newLayout: Layout, _oldItem: LayoutItem | null, newItem: LayoutItem | null) => {
        if (!newItem) return;
        const preDrag = gridLayoutBeforeDragRef.current;
        const draggedBefore = preDrag.find((l) => l.i === newItem.i);
        if (!draggedBefore) return;

        const swapTarget = preDrag.find((l) => {
            if (l.i === newItem.i) return false;
            return newItem.x < l.x + l.w && newItem.x + newItem.w > l.x
                && newItem.y < l.y + l.h && newItem.y + newItem.h > l.y;
        });

        if (swapTarget) {
            setGridLayout(preDrag.map((l) => {
                if (l.i === newItem.i) return {...l, x: swapTarget.x, y: swapTarget.y};
                if (l.i === swapTarget.i) return {...l, x: draggedBefore.x, y: draggedBefore.y};
                return l;
            }));
        } else {
            const maxX = GRID_COLS - newItem.w;
            const maxY = tiling.rows - newItem.h;
            setGridLayout(preDrag.map((l) => {
                if (l.i === newItem.i) {
                    return {...l, x: Math.max(0, Math.min(newItem.x, maxX)), y: Math.max(0, Math.min(newItem.y, maxY))};
                }
                return l;
            }));
        }
    }, [tiling.rows]);

    const handleGridLayoutChange = useCallback((_: Layout) => {}, []);
    const handleGridResizeStop = useCallback((newLayout: Layout) => { setGridLayout([...newLayout]); }, []);

    const gridRowHeight = useMemo(() => {
        const totalMargin = (tiling.rows - 1) * GRID_MARGIN[1];
        return Math.max(30, (gridHeight - totalMargin) / tiling.rows);
    }, [gridHeight, tiling.rows]);

    // -----------------------------------------------------------------------
    // Render
    // -----------------------------------------------------------------------
    if (videos.length === 0) {
        return (
            <Box sx={{display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'text.secondary'}}>
                <Typography>{t("noVideosLoaded")}</Typography>
            </Box>
        );
    }

    const framePadLen = Math.max(String(totalFrames).length, 1);
    const initialFrameText = 'F' + String(currentFrame).padStart(framePadLen, '0');

    // Compute initial time text for overlay SSR
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
        <Box sx={{display: 'flex', flexDirection: 'column', height: '100%', width: '100%'}}>
            {/* Video grid */}
            <Box
                ref={gridContainerRef}
                sx={{
                    flex: 1,
                    position: 'relative',
                    overflow: 'hidden',
                    backgroundColor: '#0a0a0a',
                    minHeight: 0,
                    '& .react-grid-placeholder': {
                        backgroundColor: 'primary.main',
                        opacity: 0.15,
                        borderRadius: '4px',
                    },
                    '& .react-resizable-handle': {
                        zIndex: 10,
                    },
                }}
            >
                <ReactGridLayout
                    width={gridWidth}
                    layout={gridLayout}
                    gridConfig={{
                        cols: GRID_COLS,
                        rowHeight: gridRowHeight,
                        margin: GRID_MARGIN,
                        containerPadding: [0, 0] as [number, number],
                    }}
                    dragConfig={{enabled: true}}
                    resizeConfig={{enabled: true}}
                    compactor={noCompactor}
                    onLayoutChange={handleGridLayoutChange}
                    onDragStart={handleGridDragStart}
                    onDragStop={handleGridDragStop}
                    onResizeStop={handleGridResizeStop}
                >
                    {videos.map((video) => (
                        <div
                            key={video.videoId}
                            style={{
                                position: 'relative',
                                overflow: 'hidden',
                                backgroundColor: '#000',
                                borderRadius: '4px',
                                border: '1px solid rgba(255,255,255,0.15)',
                            }}
                        >
                            <video
                                ref={(el) => setVideoRef(video.videoId, el)}
                                src={video.streamUrl}
                                preload="auto"
                                muted
                                playsInline
                                style={{width: '100%', height: '100%', objectFit: 'contain'}}
                                onLoadedMetadata={handleLoadedMetadata}
                            />

                            {settings.showOverlays && (
                                <>
                                    {/* FRAME NUMBER */}
                                    <Box
                                        ref={(el: HTMLElement | null) => setFrameOverlayRef(video.videoId, el)}
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
                                        {video.videoId}
                                    </Box>

                                    {/* TIMECODE */}
                                    <Tooltip title={timestampsAreReal ? t("timestampFromRecording") : t("estimatedFromFrameNumber")} placement="top-end">
                                        <Box
                                            ref={(el: HTMLElement | null) => setTimeOverlayRef(video.videoId, el)}
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
                    ))}
                </ReactGridLayout>
            </Box>

            {!allReady && videos.length > 0 && (
                <Box sx={{textAlign: 'center', py: 0.5, backgroundColor: theme.palette.warning.dark, color: '#fff'}}>
                    <Typography variant="caption">{t("loadingVideos", {ready: videosReady, total: videos.length})}</Typography>
                </Box>
            )}
        </Box>
    );
};
