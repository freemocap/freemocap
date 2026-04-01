import React, { useCallback, useEffect, useRef, useState, useMemo } from 'react';
import { Box, Tooltip, Typography, useTheme } from '@mui/material';
import ReactGridLayout, { noCompactor } from 'react-grid-layout';
import type { Layout, LayoutItem } from 'react-grid-layout';
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';
import { PlaybackControls } from './PlaybackControls';
import { useTranslation } from 'react-i18next';

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
    recordingFps?: number;
    /** Per-camera frame timestamps in seconds from recording start, loaded from CSV files */
    frameTimestamps?: Record<string, number[]> | null;
    /** null = auto-optimize, number = manual column count */
    manualColumns: number | null;
    /** Increment to force layout reset */
    resetKey: number;
    /** Frame to seek to once all videos are ready (default 0) */
    initialFrame?: number;
    /** Called when the current frame changes (throttled to ~5Hz) */
    onFrameChange?: (frame: number) => void;
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

function formatTimecodeFromSeconds(seconds: number, fps: number): string {
    if (fps <= 0) return '00:00:00:00';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    const f = Math.floor((seconds % 1) * fps);
    const pad = (n: number) => n.toString().padStart(2, '0');
    return `${pad(h)}:${pad(m)}:${pad(s)}:${pad(f)}`;
}

function formatSeconds(frame: number, fps: number): string {
    if (fps <= 0) return '0.000s';
    return `${(frame / fps).toFixed(3)}s`;
}

/**
 * Frame-locked multi-video player using a "leader" video element as the
 * canonical time source. All other videos sync to the leader.
 *
 * SYNC STRATEGY:
 * - The first video is the "leader" and drives canonical time via its
 *   native currentTime property, which naturally accounts for decode
 *   latency, buffering, and rate changes.
 * - The rAF loop reads leader.currentTime to derive the frame number.
 * - Follower videos are corrected ONLY when they drift beyond a generous
 *   tolerance (2 frames), avoiding micro-stutter from frequent seeks.
 * - Overlays update via direct DOM manipulation (zero React re-renders).
 * - React state for controls/slider updates at ~5Hz.
 */
export const SyncedVideoPlayer: React.FC<SyncedVideoPlayerProps> = ({ videos, recordingFps, frameTimestamps, manualColumns, resetKey, initialFrame = 0, onFrameChange }) => {
    const theme = useTheme();
    const { t } = useTranslation();
    const videoRefs = useRef<Map<string, HTMLVideoElement>>(new Map());

    // Direct DOM refs for overlays — updated WITHOUT React re-renders
    const frameOverlayRefs = useRef<Map<string, HTMLElement>>(new Map());
    const timeOverlayRefs = useRef<Map<string, HTMLElement>>(new Map());

    // Playback refs (rAF loop reads these, never stale)
    const isPlayingRef = useRef(false);
    const currentFrameRef = useRef(0);
    const totalFramesRef = useRef(0);
    const fpsRef = useRef(recordingFps || 30);
    const playbackRateRef = useRef(1);
    const rafRef = useRef<number | null>(null);
    const settingsRef = useRef<PlaybackSettings>({ showOverlays: true, timestampFormat: 'seconds' });
    const frameTimestampsRef = useRef<Record<string, number[]> | null>(null);
    const onFrameChangeRef = useRef(onFrameChange);
    onFrameChangeRef.current = onFrameChange;
    const didSeekInitialRef = useRef(false);

    // Leader-based sync: first video is the time authority
    const leaderIdRef = useRef<string | null>(null);

    // Follower drift correction: generous tolerance to avoid stutter.
    // Only correct followers that are more than 2 frames away from leader.
    const FOLLOWER_DRIFT_TOLERANCE_FRAMES = 2;
    // Check followers every N rAF ticks (~250ms at 60fps)
    const FOLLOWER_CHECK_INTERVAL = 15;
    const followerCheckCounter = useRef(0);

    // Throttle React state updates to ~5Hz
    const lastReactUpdateRef = useRef(0);
    const REACT_UPDATE_INTERVAL_MS = 200;

    // Slider drag state
    const isDraggingRef = useRef(false);
    const wasPlayingBeforeDragRef = useRef(false);

    // React state — ONLY for controls/slider, NOT updated per-frame
    const [isPlaying, setIsPlaying] = useState(false);
    const [currentFrame, setCurrentFrame] = useState(0);
    const [totalFrames, setTotalFrames] = useState(0);
    const [duration, setDuration] = useState(0);
    const [playbackRate, setPlaybackRate] = useState(1);
    const [videosReady, setVideosReady] = useState(0);
    const [settings, setSettings] = useState<PlaybackSettings>({
        showOverlays: true,
        timestampFormat: 'timecode',
    });
    const [isLooping, setIsLooping] = useState(false);
    const isLoopingRef = useRef(false);

    const fps = recordingFps || 30;
    const allReady = videosReady >= videos.length && videos.length > 0;
    const currentTime = fpsRef.current > 0 ? currentFrameRef.current / fpsRef.current : 0;

    // -----------------------------------------------------------------------
    // Grid layout (same auto-tiling as CameraViewsGrid)
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
        if (n <= 1) return { cols: 1, rows: 1 };
        let bestCols = 1;
        let bestArea = 0;
        for (let cols = 1; cols <= n; cols++) {
            const rows = Math.ceil(n / cols);
            const cellW = (w - GRID_MARGIN[0] * (cols - 1)) / cols;
            const cellH = (h - GRID_MARGIN[1] * (rows - 1)) / rows;
            if (cellW < 80 || cellH < 60) continue;
            const area = n * cellW * cellH;
            if (area > bestArea) { bestArea = area; bestCols = cols; }
        }
        return { cols: bestCols, rows: Math.ceil(n / bestCols) };
    };

    const prevTilingRef = useRef({ cols: 1, rows: 1 });
    const tiling = useMemo(() => {
        const candidate = manualColumns !== null
            ? { cols: Math.max(1, Math.min(manualColumns, videos.length || 1)), rows: Math.ceil((videos.length || 1) / Math.max(1, Math.min(manualColumns, videos.length || 1))) }
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
                if (l.i === newItem.i) return { ...l, x: swapTarget.x, y: swapTarget.y };
                if (l.i === swapTarget.i) return { ...l, x: draggedBefore.x, y: draggedBefore.y };
                return l;
            }));
        } else {
            const maxX = GRID_COLS - newItem.w;
            const maxY = tiling.rows - newItem.h;
            setGridLayout(preDrag.map((l) => {
                if (l.i === newItem.i) {
                    return { ...l, x: Math.max(0, Math.min(newItem.x, maxX)), y: Math.max(0, Math.min(newItem.y, maxY)) };
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

    // Keep refs in sync with props/state
    useEffect(() => { settingsRef.current = settings; }, [settings]);
    useEffect(() => { isLoopingRef.current = isLooping; }, [isLooping]);
    useEffect(() => { frameTimestampsRef.current = frameTimestamps ?? null; }, [frameTimestamps]);
    useEffect(() => {
        if (recordingFps && recordingFps > 0) fpsRef.current = recordingFps;
    }, [recordingFps]);

    // Elect leader whenever video list changes
    useEffect(() => {
        leaderIdRef.current = videos.length > 0 ? videos[0].videoId : null;
    }, [videos]);

    // -----------------------------------------------------------------------
    // Direct DOM overlay updates — fast, no React involved
    // -----------------------------------------------------------------------
    const updateOverlays = useCallback((frame: number) => {
        const s = settingsRef.current;
        const ts = frameTimestampsRef.current;
        const padLen = Math.max(String(totalFramesRef.current).length, 1);
        const frameText = 'F' + String(frame).padStart(padLen, '0');

        let timeText: string;
        if (ts) {
            const firstKey = Object.keys(ts)[0];
            const camTs = firstKey ? ts[firstKey] : null;
            if (camTs && frame < camTs.length) {
                const realSec = camTs[frame];
                timeText = s.timestampFormat === 'timecode'
                    ? formatTimecodeFromSeconds(realSec, fpsRef.current)
                    : `${realSec.toFixed(3)}s`;
            } else {
                timeText = '~' + (s.timestampFormat === 'timecode'
                    ? formatTimecode(frame, fpsRef.current)
                    : formatSeconds(frame, fpsRef.current));
            }
        } else {
            timeText = '~' + (s.timestampFormat === 'timecode'
                ? formatTimecode(frame, fpsRef.current)
                : formatSeconds(frame, fpsRef.current));
        }

        frameOverlayRefs.current.forEach((el) => { el.textContent = frameText; });
        timeOverlayRefs.current.forEach((el) => { el.textContent = timeText; });
    }, []);

    // -----------------------------------------------------------------------
    // Ref registration
    // -----------------------------------------------------------------------
    const setVideoRef = useCallback((videoId: string, el: HTMLVideoElement | null) => {
        if (el) videoRefs.current.set(videoId, el);
        else videoRefs.current.delete(videoId);
    }, []);

    const setFrameOverlayRef = useCallback((videoId: string, el: HTMLElement | null) => {
        if (el) frameOverlayRefs.current.set(videoId, el);
        else frameOverlayRefs.current.delete(videoId);
    }, []);

    const setTimeOverlayRef = useCallback((videoId: string, el: HTMLElement | null) => {
        if (el) timeOverlayRefs.current.set(videoId, el);
        else timeOverlayRefs.current.delete(videoId);
    }, []);

    // -----------------------------------------------------------------------
    // Seek all videos to a frame (used when PAUSED / stepping only)
    // -----------------------------------------------------------------------
    const seekAllToFrame = useCallback((frame: number) => {
        const clamped = Math.max(0, Math.min(frame, totalFramesRef.current - 1));
        const targetTime = fpsRef.current > 0 ? clamped / fpsRef.current : 0;
        videoRefs.current.forEach((el) => { el.currentTime = targetTime; });
        currentFrameRef.current = clamped;
        setCurrentFrame(clamped);
        onFrameChangeRef.current?.(clamped);
        updateOverlays(clamped);
    }, [updateOverlays]);

    // -----------------------------------------------------------------------
    // Native play/pause
    // -----------------------------------------------------------------------
    const playAllVideos = useCallback(() => {
        const rate = playbackRateRef.current;
        // Play leader first so it starts decoding immediately
        const leaderId = leaderIdRef.current;
        const leader = leaderId ? videoRefs.current.get(leaderId) : null;
        if (leader) {
            leader.playbackRate = rate;
            leader.play().catch(() => {});
        }
        videoRefs.current.forEach((el, id) => {
            if (id === leaderId) return;
            el.playbackRate = rate;
            el.play().catch(() => {});
        });
    }, []);

    const pauseAllVideos = useCallback(() => {
        videoRefs.current.forEach((el) => { el.pause(); });
    }, []);

    // -----------------------------------------------------------------------
    // rAF playback loop — reads leader.currentTime as the time source.
    //
    // This eliminates the wall-clock-vs-decode-pipeline fight that causes
    // stutter. The leader's currentTime naturally accounts for buffering,
    // decode latency, and rate changes. We just read it and derive frames.
    // -----------------------------------------------------------------------
    const tick = useCallback((timestamp: DOMHighResTimeStamp) => {
        if (!isPlayingRef.current) return;

        const leaderId = leaderIdRef.current;
        const leader = leaderId ? videoRefs.current.get(leaderId) : null;
        if (!leader) {
            rafRef.current = requestAnimationFrame(tick);
            return;
        }

        const leaderTime = leader.currentTime;
        const newFrame = leaderTime * fpsRef.current;

        // End of video — loop back to start or stop
        if (newFrame >= totalFramesRef.current) {
            if (isLoopingRef.current) {
                // Pause all videos, seek cleanly to frame 0, then restart playback.
                // Seeking while videos are still playing causes the browser's decode
                // pipeline to stall, producing choppy playback on subsequent loops.
                pauseAllVideos();
                const targetTime = 0;
                videoRefs.current.forEach((el) => { el.currentTime = targetTime; });
                currentFrameRef.current = 0;
                followerCheckCounter.current = 0;
                updateOverlays(0);
                setCurrentFrame(0);
                playAllVideos();
                rafRef.current = requestAnimationFrame(tick);
                return;
            }
            pauseAllVideos();
            isPlayingRef.current = false;
            const endFrame = totalFramesRef.current - 1;
            currentFrameRef.current = endFrame;
            updateOverlays(endFrame);
            setIsPlaying(false);
            setCurrentFrame(endFrame);
            return;
        }

        const intFrame = Math.floor(newFrame);
        const prevIntFrame = Math.floor(currentFrameRef.current);
        currentFrameRef.current = newFrame;

        // Update DOM overlays on frame change
        if (intFrame !== prevIntFrame) {
            updateOverlays(intFrame);
        }

        // Throttled React update for slider (~5Hz)
        if (timestamp - lastReactUpdateRef.current >= REACT_UPDATE_INTERVAL_MS) {
            lastReactUpdateRef.current = timestamp;
            setCurrentFrame(intFrame);
            onFrameChangeRef.current?.(intFrame);
        }

        // Periodic follower drift correction — only when drift exceeds tolerance.
        // This is the key to smooth playback: let browser-native playback run
        // undisturbed and only intervene when followers genuinely desync.
        followerCheckCounter.current++;
        if (followerCheckCounter.current >= FOLLOWER_CHECK_INTERVAL) {
            followerCheckCounter.current = 0;
            const toleranceSec = FOLLOWER_DRIFT_TOLERANCE_FRAMES / fpsRef.current;
            const rate = playbackRateRef.current;
            videoRefs.current.forEach((el, id) => {
                if (id === leaderId) return;
                if (Math.abs(el.currentTime - leaderTime) > toleranceSec) {
                    el.currentTime = leaderTime;
                }
                if (Math.abs(el.playbackRate - rate) > 0.01) {
                    el.playbackRate = rate;
                }
            });
        }

        rafRef.current = requestAnimationFrame(tick);
    }, [pauseAllVideos, playAllVideos, updateOverlays]);

    const startLoop = useCallback(() => {
        followerCheckCounter.current = 0;
        lastReactUpdateRef.current = 0;
        rafRef.current = requestAnimationFrame(tick);
    }, [tick]);

    const stopLoop = useCallback(() => {
        if (rafRef.current !== null) { cancelAnimationFrame(rafRef.current); rafRef.current = null; }
    }, []);

    useEffect(() => stopLoop, [stopLoop]);

    // -----------------------------------------------------------------------
    // Metadata
    // -----------------------------------------------------------------------
    const handleLoadedMetadata = useCallback((e: React.SyntheticEvent<HTMLVideoElement>) => {
        const el = e.currentTarget;
        if (el.duration && el.duration !== Infinity) {
            const d = el.duration;
            setDuration((prev) => Math.max(prev, d));
            const frames = Math.floor(d * fpsRef.current);
            if (totalFramesRef.current === 0 || frames < totalFramesRef.current) {
                totalFramesRef.current = frames;
                setTotalFrames(frames);
            }
        }
        el.pause();
        setVideosReady((prev) => prev + 1);
    }, []);

    // -----------------------------------------------------------------------
    // Playback commands
    // -----------------------------------------------------------------------
    const handlePlayPause = useCallback(() => {
        if (isPlayingRef.current) {
            isPlayingRef.current = false;
            stopLoop();
            pauseAllVideos();
            setIsPlaying(false);
            // Snap all videos to leader's position on pause for perfect alignment
            const leaderId = leaderIdRef.current;
            const leader = leaderId ? videoRefs.current.get(leaderId) : null;
            if (leader) {
                const pauseFrame = Math.floor(leader.currentTime * fpsRef.current);
                seekAllToFrame(pauseFrame);
            }
        } else {
            if (Math.floor(currentFrameRef.current) >= totalFramesRef.current - 1) {
                seekAllToFrame(0);
            }
            isPlayingRef.current = true;
            setIsPlaying(true);
            playAllVideos();
            startLoop();
        }
    }, [seekAllToFrame, startLoop, stopLoop, playAllVideos, pauseAllVideos]);

    // Slider DRAG — pause once, then scrub as user drags
    const handleSeekDrag = useCallback((frame: number) => {
        if (!isDraggingRef.current) {
            isDraggingRef.current = true;
            wasPlayingBeforeDragRef.current = isPlayingRef.current;
            if (isPlayingRef.current) {
                isPlayingRef.current = false;
                stopLoop();
                pauseAllVideos();
            }
        }
        const clamped = Math.max(0, Math.min(frame, totalFramesRef.current - 1));
        currentFrameRef.current = clamped;
        updateOverlays(clamped);
        setCurrentFrame(clamped);
        const targetTime = fpsRef.current > 0 ? clamped / fpsRef.current : 0;
        videoRefs.current.forEach((el) => { el.currentTime = targetTime; });
    }, [stopLoop, pauseAllVideos, updateOverlays]);

    // Slider COMMIT — final seek + resume if was playing
    const handleSeekCommit = useCallback((frame: number) => {
        const clamped = Math.max(0, Math.min(frame, totalFramesRef.current - 1));
        seekAllToFrame(clamped);
        if (wasPlayingBeforeDragRef.current) {
            isPlayingRef.current = true;
            setIsPlaying(true);
            playAllVideos();
            startLoop();
        }
        isDraggingRef.current = false;
        wasPlayingBeforeDragRef.current = false;
    }, [seekAllToFrame, playAllVideos, startLoop]);

    const handleFrameStep = useCallback((delta: number) => {
        if (isPlayingRef.current) { isPlayingRef.current = false; stopLoop(); pauseAllVideos(); setIsPlaying(false); }
        seekAllToFrame(Math.floor(currentFrameRef.current) + delta);
    }, [seekAllToFrame, stopLoop, pauseAllVideos]);

    const handlePlaybackRateChange = useCallback((rate: number) => {
        playbackRateRef.current = rate;
        setPlaybackRate(rate);
        videoRefs.current.forEach((el) => { el.playbackRate = rate; });
    }, []);

    const handleSeekToStart = useCallback(() => {
        const wasPlaying = isPlayingRef.current;
        if (wasPlaying) { isPlayingRef.current = false; stopLoop(); pauseAllVideos(); }
        seekAllToFrame(0);
        if (wasPlaying) { isPlayingRef.current = true; setIsPlaying(true); playAllVideos(); startLoop(); }
    }, [seekAllToFrame, stopLoop, startLoop, playAllVideos, pauseAllVideos]);

    const handleSeekToEnd = useCallback(() => {
        if (isPlayingRef.current) { isPlayingRef.current = false; stopLoop(); pauseAllVideos(); setIsPlaying(false); }
        seekAllToFrame(totalFramesRef.current - 1);
    }, [seekAllToFrame, stopLoop, pauseAllVideos]);

    const handleToggleLoop = useCallback(() => {
        setIsLooping((prev) => !prev);
    }, []);

    // Seek to initialFrame once all videos are ready (e.g. restoring position after tab switch)
    useEffect(() => {
        if (allReady && !didSeekInitialRef.current && initialFrame > 0) {
            didSeekInitialRef.current = true;
            seekAllToFrame(initialFrame);
        }
    }, [allReady, initialFrame, seekAllToFrame]);

    // -----------------------------------------------------------------------
    // Keyboard
    // -----------------------------------------------------------------------
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
            switch (e.key) {
                case ' ': if (e.shiftKey) break; e.preventDefault(); handlePlayPause(); break;
                case 'ArrowLeft': e.preventDefault(); handleFrameStep(e.shiftKey ? -10 : -1); break;
                case 'ArrowRight': e.preventDefault(); handleFrameStep(e.shiftKey ? 10 : 1); break;
                case 'Home': e.preventDefault(); handleSeekToStart(); break;
                case 'End': e.preventDefault(); handleSeekToEnd(); break;
                case 'l': case 'L': e.preventDefault(); handleToggleLoop(); break;
            }
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [handlePlayPause, handleFrameStep, handleSeekToStart, handleSeekToEnd, handleToggleLoop]);

    // -----------------------------------------------------------------------
    // Render
    // -----------------------------------------------------------------------
    if (videos.length === 0) {
        return (
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'text.secondary' }}>
                <Typography>{t("noVideosLoaded")}</Typography>
            </Box>
        );
    }

    const framePadLen = Math.max(String(totalFrames).length, 1);
    const initialFrameText = 'F' + String(currentFrame).padStart(framePadLen, '0');

    let initialTimeText: string;
    let timestampsAreReal = false;
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
        <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', width: '100%' }}>
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
                    dragConfig={{ enabled: true }}
                    resizeConfig={{ enabled: true }}
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
                            style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                            onLoadedMetadata={handleLoadedMetadata}
                        />

                        {settings.showOverlays && (
                            <>
                                {/* FRAME NUMBER — DOM ref, updated directly */}
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

                                {/* CAMERA ID — static */}
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

                                {/* TIMECODE — DOM ref, updated directly */}
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
                <Box sx={{ textAlign: 'center', py: 0.5, backgroundColor: theme.palette.warning.dark, color: '#fff' }}>
                    <Typography variant="caption">{t("loadingVideos", { ready: videosReady, total: videos.length })}</Typography>
                </Box>
            )}

            <PlaybackControls
                isPlaying={isPlaying}
                currentTime={currentTime}
                duration={duration}
                playbackRate={playbackRate}
                currentFrame={currentFrame}
                totalFrames={totalFrames}
                fps={fps}
                recordingFps={recordingFps}
                settings={settings}
                onSettingsChange={setSettings}
                onPlayPause={handlePlayPause}
                onSeekDrag={handleSeekDrag}
                onSeekCommit={handleSeekCommit}
                onFrameStep={handleFrameStep}
                onPlaybackRateChange={handlePlaybackRateChange}
                onSeekToStart={handleSeekToStart}
                onSeekToEnd={handleSeekToEnd}
                isLooping={isLooping}
                onToggleLoop={handleToggleLoop}
            />
        </Box>
    );
};
