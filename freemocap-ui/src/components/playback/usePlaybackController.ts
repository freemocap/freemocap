import {RecordingVideoCache} from '@/services/recording/recording-video-cache';
import {useCallback, useEffect, useRef, useState} from 'react';
import type {PlaybackSettings} from './SyncedVideoPlayer';
import {ClientVideoGroup, releaseGroupFrames, type GroupFrames, type VideoEntry} from '@/services/recording/client-video-group';
import {PlaybackLabel} from '@/services/recording/playback-label';
import {FrameLookahead} from '@/services/recording/frame-lookahead';
import {type PlaybackManifest, type PlaybackRun, type PlaybackMedia} from '@/services/recording/playback-data';
import type {PlaybackBundle} from '@/store/slices/playback-data/playback-data-slice';

interface UsePlaybackControllerArgs {
    videos: VideoEntry[]; recordingId: string | null; recordingParentDirectory: string | null | undefined;
    bundle: Pick<PlaybackBundle, 'manifest' | 'media' | 'videos'> | null;
    reloadManifest: () => void;
    cacheBudgetBytes: number | null;
    onFrameChange?: (frame: number) => void;
}

export function usePlaybackController({videos, recordingId, recordingParentDirectory, bundle, reloadManifest, cacheBudgetBytes, onFrameChange}: UsePlaybackControllerArgs) {
    const [manifest, setManifest] = useState<PlaybackManifest | null>(null);
    const [media, setMedia] = useState<PlaybackMedia[]>([]);
    const recordingCache = useRef<RecordingVideoCache | null>(null);
    const [decoderGroup, setDecoderGroup] = useState<ClientVideoGroup | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [isPlaying, setIsPlaying] = useState(false);
    const [currentFrame, setCurrentFrame] = useState(0);
    const [requestedFrame, setRequestedFrame] = useState(0);
    const [playbackRate, setPlaybackRate] = useState(1);
    const [isLooping, setIsLooping] = useState(false);
    const [videosReady, setVideosReady] = useState(0);
    const [settings, setSettings] = useState<PlaybackSettings>({showOverlays: true, timestampFormat: 'seconds'});
    const canvases = useRef(new Map<string, HTMLCanvasElement>());
    const frameLabels = useRef(new Map<string, PlaybackLabel>());
    const settingsRef = useRef(settings);
    settingsRef.current = settings;
    const requestedFrameRef = useRef(0);
    const presentedTime = useRef<number | null>(null);
    const currentFrameRef = useRef(0);
    const frameTimestampsRef = useRef<Record<string, number[]> | null>(null);
    const onFrameChangeRef = useRef(onFrameChange);
    onFrameChangeRef.current = onFrameChange;
    const videosRef = useRef(videos);
    videosRef.current = videos;
    const videoKey = JSON.stringify(videos);
    const leader = media.find(item => item.video_filename === videos[0]?.filename);
    const timeline = leader?.timeline;
    const totalFrames = timeline?.frame_numbers.length ?? 0;
    const fps = leader?.nominal_fps ?? 30;
    const times = timeline?.timestamps_s;
    const currentTime = times?.[currentFrame] ?? 0;
    const duration = times?.length ? times[times.length - 1] : 0;
    useEffect(() => {
        setManifest(null); setMedia([]); setError(null); setIsPlaying(false);
        setVideosReady(0); setCurrentFrame(0); setRequestedFrame(0);
        requestedFrameRef.current = 0; currentFrameRef.current = 0; presentedTime.current = null;
    }, [recordingId, recordingParentDirectory]);

    useEffect(() => {
        if (!bundle) return;
        setManifest(bundle.manifest); setMedia(bundle.media);
    }, [bundle]);

    useEffect(() => {
        if (isPlaying) requestedFrameRef.current = currentFrameRef.current;
        setIsPlaying(false); setRequestedFrame(requestedFrameRef.current); setVideosReady(0);
        presentedTime.current = null;
        canvases.current.forEach(canvas => canvas.getContext('2d')?.clearRect(0, 0, canvas.width, canvas.height));
    }, [media, videoKey]);

    useEffect(() => {
        const cache = bundle?.media.length && cacheBudgetBytes ? new RecordingVideoCache(bundle.media.length, cacheBudgetBytes) : null;
        recordingCache.current = cache;
        return () => {cache?.close(); recordingCache.current = null;};
    }, [bundle, recordingId, recordingParentDirectory, cacheBudgetBytes]);

    useEffect(() => {
        if (!videosRef.current.length || !recordingCache.current) {setDecoderGroup(null); return;}
        const group = recordingCache.current.getGroup(videosRef.current);
        let active = true;
        setDecoderGroup(group);
        void group.ready.catch(failure => {if (active) setError(String(failure));});
        return () => {active = false;};
    }, [videoKey, bundle, recordingId, recordingParentDirectory, cacheBudgetBytes]);

    useEffect(() => {
        const cache = recordingCache.current;
        if (!cache || !bundle || isPlaying || !videosReady) return;
        let active = true;
        const allVideos = Object.values(bundle.videos.sources).flatMap(source => source.videos);
        void cache.prefetch(allVideos, () => active).catch(failure => {if (active) setError(String(failure));});
        return () => {active = false;};
    }, [bundle, isPlaying, videosReady]);

    useEffect(() => {
        if (!decoderGroup || !leader || !times) return;
        let active = true;
        let timer: ReturnType<typeof setTimeout> | undefined;
        let buffer: FrameLookahead<GroupFrames> | null = null;
        let lastUiUpdate = 0;
        const fail = (failure: unknown): void => {
            if (!active) return;
            setError(String(failure)); setIsPlaying(false);
        };
        const present = (frames: GroupFrames, forceUi: boolean): void => {
            const frameNumber = frames[0].ordinal;
            const time = times[frameNumber];
            if (time === undefined) throw new Error('Frame is outside the recording timeline');
            const targets = decoderGroup.videos.map(video => {
                const canvas = canvases.current.get(video.videoId);
                if (!canvas) throw new Error(`Missing playback canvas for ${video.filename}`);
                const context = canvas.getContext('2d');
                if (!context) throw new Error('Canvas rendering is unavailable');
                return {video, canvas, context};
            });
            const seconds = Math.floor(time);
            const timecode = [Math.floor(seconds / 3600), Math.floor(seconds / 60) % 60, seconds % 60,
                Math.floor((time - seconds) * fps)].map(value => String(value).padStart(2, '0')).join(':');
            const timestamp = settingsRef.current.timestampFormat === 'timecode' ? timecode : `${time.toFixed(3)} s`;
            const labelText = `F${String(frameNumber).padStart(String(totalFrames).length, '0')}  |  ${timestamp}`;
            targets.forEach(({video, canvas, context}, index) => {
                const bitmap = frames[index].bitmap;
                if (canvas.width !== bitmap.width) canvas.width = bitmap.width;
                if (canvas.height !== bitmap.height) canvas.height = bitmap.height;
                context.drawImage(bitmap, 0, 0);

                frameLabels.current.get(video.videoId)?.draw(labelText);
            });
            presentedTime.current = time;
            currentFrameRef.current = frameNumber;
            onFrameChangeRef.current?.(frameNumber);
            if (forceUi || performance.now() - lastUiUpdate >= 100) {
                setCurrentFrame(frameNumber); lastUiUpdate = performance.now();
            }
        };
        const run = async (): Promise<void> => {
            const count = await decoderGroup.ready;
            if (!active) return;
            if (count !== totalFrames) throw new Error(`Video has ${count} frames but its recording timeline has ${totalFrames}`);
            const start = isPlaying ? currentFrameRef.current : requestedFrame;
            const first = await decoderGroup.read(start);
            try {
                if (!active) return;
                setError(null);
                if (!isPlaying) {present(first, true); setVideosReady(first.length); return;}
                const groupBytes = first.reduce((sum, frame) => sum + frame.bitmap.width * frame.bitmap.height * 4, 0);
                const capacity = Math.min(Math.ceil(fps * 0.5), Math.floor((cacheBudgetBytes! / 4) / groupBytes) - 2);
                if (capacity < 1) throw new Error('Video group exceeds the playback buffer memory budget');
                buffer = new FrameLookahead({start: start + 1, end: totalFrames, capacity,
                    load: ordinal => decoderGroup.read(ordinal), release: releaseGroupFrames});
                await buffer.fill();
                if (!active) return;
                present(first, true); setVideosReady(first.length);
                const interval = 1000 / (fps * playbackRate);
                let deadline = performance.now() + interval;
                let stalled = false;
                const tick = (): void => {
                    if (!active || !buffer) return;
                    try {
                        const now = performance.now();
                        if (now >= deadline) {
                            const frames = buffer.take();
                            if (frames) {
                                try {present(frames, frames[0].ordinal === totalFrames - 1);} finally {releaseGroupFrames(frames);}
                                deadline = stalled || now - deadline > interval ? now + interval : deadline + interval;
                                stalled = false;
                                void buffer.fill().catch(fail);
                            } else if (buffer.finished) {
                                if (isLooping) {
                                    buffer = new FrameLookahead({start: 0, end: totalFrames, capacity,
                                        load: ordinal => decoderGroup.read(ordinal), release: releaseGroupFrames});
                                    void buffer.fill().catch(fail); stalled = true;
                                } else {requestedFrameRef.current = currentFrameRef.current; setRequestedFrame(currentFrameRef.current); setIsPlaying(false); return;}
                            } else {stalled = true;}
                        }
                        timer = setTimeout(tick, stalled ? interval : Math.max(1, deadline - performance.now()));
                    } catch (failure) {fail(failure);}
                };
                timer = setTimeout(tick, interval);
            } finally {releaseGroupFrames(first);}
        };
        timer = setTimeout(() => void run().catch(fail), isPlaying ? 0 : 80);
        return () => {
            active = false; clearTimeout(timer);
            if (buffer) void buffer.close().catch(fail);
        };
    }, [decoderGroup, media, requestedFrame, isPlaying, isLooping, playbackRate, leader, times, totalFrames, fps, cacheBudgetBytes]);
    const seek = useCallback((frame: number): void => {
        setIsPlaying(false);
        requestedFrameRef.current = Math.max(0, Math.min(Math.round(frame), totalFrames - 1));
        setRequestedFrame(requestedFrameRef.current);
    }, [totalFrames]);
    const setVideoRef = useCallback((id: string, canvas: HTMLCanvasElement | null): void => {
        if (canvas) canvases.current.set(id, canvas); else canvases.current.delete(id);
    }, []);
    const setFrameOverlayRef = useCallback((id: string, element: HTMLCanvasElement | null): void => {
        if (element) frameLabels.current.set(id, new PlaybackLabel(element)); else frameLabels.current.delete(id);
    }, []);
    const getRecordingTime = useCallback((): number | null => presentedTime.current, []);
    const setPlaybackRun = useCallback((run: PlaybackRun): void => setMedia(run.media), []);
    const handlePlayPause = useCallback((): void => {
        if (isPlaying) {requestedFrameRef.current = currentFrameRef.current; setRequestedFrame(currentFrameRef.current);}
        else if (currentFrameRef.current >= totalFrames - 1) {currentFrameRef.current = 0; requestedFrameRef.current = 0; setRequestedFrame(0);}
        setIsPlaying(value => !value);
    }, [isPlaying, totalFrames]);
    useEffect(() => {
        const onKey = (event: KeyboardEvent): void => {
            const element = event.target;
            if (element instanceof HTMLElement && (element.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT', 'BUTTON'].includes(element.tagName))) return;
            switch (event.key) {
                case ' ': event.preventDefault(); handlePlayPause(); break;
                case 'ArrowLeft': event.preventDefault(); seek((isPlaying ? currentFrameRef.current : requestedFrameRef.current) - 1); break;
                case 'ArrowRight': event.preventDefault(); seek((isPlaying ? currentFrameRef.current : requestedFrameRef.current) + 1); break;
                case 'Home': event.preventDefault(); seek(0); break;
                case 'End': event.preventDefault(); seek(totalFrames - 1); break;
            }
        };
        window.addEventListener('keydown', onKey);
        return () => window.removeEventListener('keydown', onKey);
    }, [handlePlayPause, seek, isPlaying, totalFrames]);
    return {
        manifest, setPlaybackRun, reloadManifest, error, getRecordingTime,
        seekFrame: isPlaying ? currentFrame : requestedFrame,
        isPlaying, currentFrame, totalFrames, duration, playbackRate, fps, currentTime, settings,
        isLooping, videosReady, allReady: videosReady === videos.length && videos.length > 0,
        erroredVideos: new Set<string>(), setSettings,
        handlePlayPause, isSeeking: requestedFrame !== currentFrame,
        handleSeekDrag: seek, handleSeekCommit: seek,
        handleFrameStep: (delta: number): void => seek((isPlaying ? currentFrameRef.current : requestedFrameRef.current) + delta),
        handlePlaybackRateChange: setPlaybackRate,
        handleSeekToStart: (): void => seek(0), handleSeekToEnd: (): void => seek(totalFrames - 1),
        handleToggleLoop: (): void => setIsLooping(value => !value),
        setVideoRef, setFrameOverlayRef,
        frameTimestampsRef, currentFrameRef,
    };
}

export type PlaybackController = ReturnType<typeof usePlaybackController>;
