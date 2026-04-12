import {useCallback, useEffect, useRef, useState} from 'react';
import type {PlaybackSettings} from './SyncedVideoPlayer';

interface VideoEntry {
    videoId: string;
    filename: string;
    streamUrl: string;
}

interface UsePlaybackControllerArgs {
    videos: VideoEntry[];
    recordingFps?: number;
    frameTimestamps?: Record<string, number[]> | null;
    initialFrame?: number;
    onFrameChange?: (frame: number) => void;
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

export function usePlaybackController({
    videos,
    recordingFps,
    frameTimestamps,
    initialFrame = 0,
    onFrameChange,
}: UsePlaybackControllerArgs) {
    const videoRefs = useRef<Map<string, HTMLVideoElement>>(new Map());
    const frameOverlayRefs = useRef<Map<string, HTMLElement>>(new Map());
    const timeOverlayRefs = useRef<Map<string, HTMLElement>>(new Map());

    // Playback refs (rAF loop reads these, never stale)
    const isPlayingRef = useRef(false);
    const currentFrameRef = useRef(0);
    const totalFramesRef = useRef(0);
    const fpsRef = useRef(recordingFps || 30);
    const playbackRateRef = useRef(1);
    const rafRef = useRef<number | null>(null);
    const settingsRef = useRef<PlaybackSettings>({showOverlays: true, timestampFormat: 'seconds'});
    const frameTimestampsRef = useRef<Record<string, number[]> | null>(null);
    const onFrameChangeRef = useRef(onFrameChange);
    onFrameChangeRef.current = onFrameChange;
    const didSeekInitialRef = useRef(false);

    // Leader-based sync
    const leaderIdRef = useRef<string | null>(null);
    const FOLLOWER_DRIFT_TOLERANCE_FRAMES = 2;
    const FOLLOWER_CHECK_INTERVAL = 15;
    const followerCheckCounter = useRef(0);

    // Throttle React state updates to ~5Hz
    const lastReactUpdateRef = useRef(0);
    const REACT_UPDATE_INTERVAL_MS = 200;

    // Slider drag state
    const isDraggingRef = useRef(false);
    const wasPlayingBeforeDragRef = useRef(false);

    // React state — ONLY for controls/slider
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

    // Keep refs in sync
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

    // Direct DOM overlay updates
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

    // Seek all videos to a frame
    const seekAllToFrame = useCallback((frame: number) => {
        const clamped = Math.max(0, Math.min(frame, totalFramesRef.current - 1));
        const targetTime = fpsRef.current > 0 ? clamped / fpsRef.current : 0;
        videoRefs.current.forEach((el) => { el.currentTime = targetTime; });
        currentFrameRef.current = clamped;
        setCurrentFrame(clamped);
        onFrameChangeRef.current?.(clamped);
        updateOverlays(clamped);
    }, [updateOverlays]);

    // Native play/pause
    const playAllVideos = useCallback(() => {
        const rate = playbackRateRef.current;
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

    // rAF playback loop
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

        if (newFrame >= totalFramesRef.current) {
            if (isLoopingRef.current) {
                pauseAllVideos();
                videoRefs.current.forEach((el) => { el.currentTime = 0; });
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

        if (intFrame !== prevIntFrame) {
            updateOverlays(intFrame);
        }

        if (timestamp - lastReactUpdateRef.current >= REACT_UPDATE_INTERVAL_MS) {
            lastReactUpdateRef.current = timestamp;
            setCurrentFrame(intFrame);
            onFrameChangeRef.current?.(intFrame);
        }

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

    // Metadata handler — called by video elements via onLoadedMetadata
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

    // Playback commands
    const handlePlayPause = useCallback(() => {
        if (isPlayingRef.current) {
            isPlayingRef.current = false;
            stopLoop();
            pauseAllVideos();
            setIsPlaying(false);
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

    // Seek to initialFrame once all videos are ready
    useEffect(() => {
        if (allReady && !didSeekInitialRef.current && initialFrame > 0) {
            didSeekInitialRef.current = true;
            seekAllToFrame(initialFrame);
        }
    }, [allReady, initialFrame, seekAllToFrame]);

    // Keyboard shortcuts
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

    // Ref registration callbacks
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

    return {
        // State
        isPlaying,
        currentFrame,
        totalFrames,
        duration,
        playbackRate,
        fps,
        currentTime,
        settings,
        isLooping,
        allReady,
        videosReady,

        // Setters
        setSettings,

        // Handlers
        handlePlayPause,
        handleSeekDrag,
        handleSeekCommit,
        handleFrameStep,
        handlePlaybackRateChange,
        handleSeekToStart,
        handleSeekToEnd,
        handleToggleLoop,
        handleLoadedMetadata,

        // Ref registration
        setVideoRef,
        setFrameOverlayRef,
        setTimeOverlayRef,

        // Internal refs exposed for SyncedVideoPlayer overlay rendering
        settingsRef,
        frameTimestampsRef,
        fpsRef,
        currentFrameRef,
        totalFramesRef,
    };
}

export type PlaybackController = ReturnType<typeof usePlaybackController>;
