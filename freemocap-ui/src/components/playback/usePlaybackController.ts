import {MAX_PRESENTATION_BYTES} from '@/services/recording/playback-budget';
import {PlaybackClock} from '@/services/recording/playback-clock';
import {ScheduledRenderer} from '@/services/server/server-helpers/scheduled-renderer';
import {RecordingVideoCache} from '@/services/recording/recording-video-cache';
import {PlaybackSource, PlaybackResolution} from '@/services/recording/playback-protocol';
import {serverUrls} from '@/services';
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
    const renderers = useRef(new WeakMap<HTMLCanvasElement, ScheduledRenderer>());
    const frameLabels = useRef(new Map<string, PlaybackLabel>());
    const settingsRef = useRef(settings);
    settingsRef.current = settings;
    const requestedFrameRef = useRef(0);
    const presentedTime = useRef<number | null>(null);
    const measuredFps = useRef<number | null>(null);
    const playbackClock = useRef<PlaybackClock | null>(null);
    const bitmapFrames = useRef<() => number[]>(() => []);
    const currentFrameRef = useRef(0);
    const frameTimestampsRef = useRef<Record<string, number[]> | null>(null);
    const onFrameChangeRef = useRef(onFrameChange);
    onFrameChangeRef.current = onFrameChange;
    const videosRef = useRef(videos);
    videosRef.current = videos;
    const videoKey = JSON.stringify(videos);
    const selectedSource = Object.entries(bundle?.videos.sources ?? {}).find(([, value]) =>
        value.videos.some(video => video.streamUrl === videos[0]?.streamUrl))?.[0];
    const leader = media.find(item => item.video_source === selectedSource && item.video_filename === videos[0]?.filename);
    const timeline = leader?.timeline;
    const totalFrames = timeline?.frame_numbers.length ?? 0;
    const fps = leader?.nominal_fps ?? 30;
    const times = timeline?.timestamps_s;
    const currentTime = times?.[currentFrame] ?? 0;
    const duration = times?.length ? times[times.length - 1] : 0;
    useEffect(() => {
        measuredFps.current = null; playbackClock.current = null;
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
    }, [videoKey]);

    useEffect(() => {
        const url = new URL(serverUrls.getHttpUrl());
        url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
        url.pathname = `/websocket/playback/${encodeURIComponent(recordingId ?? '')}`;
        if (recordingParentDirectory) url.searchParams.set('recording_parent_directory', recordingParentDirectory);
        const sourceCount = Object.values(bundle?.videos.sources ?? {}).filter(source => source.valid && source.videos.length).length;
        const cache = sourceCount && recordingId && cacheBudgetBytes
            ? new RecordingVideoCache(url.toString(), sourceCount, cacheBudgetBytes) : null;
        recordingCache.current = cache;
        return () => {cache?.close(); recordingCache.current = null;};
    }, [bundle, recordingId, recordingParentDirectory, cacheBudgetBytes]);

    useEffect(() => {
        if (!videosRef.current.length || !recordingCache.current) {setDecoderGroup(null); return;}
        const selected = Object.entries(bundle?.videos.sources ?? {}).find(([, source]) =>
            source.videos.some(video => video.streamUrl === videosRef.current[0]?.streamUrl));
        const selectedSource = selected?.[1];
        if (selectedSource && !selectedSource.valid) {
            setDecoderGroup(null);
            setError('This synchronized video group is incomplete or has unequal frame counts. See the recording resource errors.');
            return;
        }
        setError(null);
        const source = Object.values(PlaybackSource).find(value => value === selected?.[0]);
        if (!source) {setError('Selected videos have no playback source'); setDecoderGroup(null); return;}
        const group = recordingCache.current.getGroup(videosRef.current, source);
        let active = true;
        setDecoderGroup(group);
        void group.ready.catch(failure => {if (active) setError(String(failure));});
        return () => {active = false;};
    }, [videoKey, bundle, recordingId, recordingParentDirectory, cacheBudgetBytes]);

    useEffect(() => {
        if (!decoderGroup || decoderGroup.videos.length !== videos.length
            || decoderGroup.videos.some((video, index) => video.videoId !== videos[index]?.videoId
                || video.streamUrl !== videos[index]?.streamUrl) || !leader || !times) return;
        let active = true;
        let timer: ReturnType<typeof setTimeout> | undefined;
        if (isPlaying) measuredFps.current = null;
        let buffer: FrameLookahead<GroupFrames> | null = null;
        let displayedFrame: number | null = null;
        const resolution = isPlaying ? PlaybackResolution.Preview : PlaybackResolution.Detail;
        bitmapFrames.current = () => [...(displayedFrame === null ? [] : [displayedFrame]),
            ...(buffer?.buffered.map(frames => frames[0].ordinal) ?? [])];
        let cameraRenderers: ScheduledRenderer[] = [];
        let lastUiUpdate = 0;
        const fail = (failure: unknown): void => {
            if (!active) return;
            setError(String(failure)); setIsPlaying(false);
        };
        const present = async (frames: GroupFrames, forceUi: boolean): Promise<void> => {
            if (!active) return;
            await Promise.all(frames.map(frame => frame.renderer.present(frame.image)));
            if (!active) return;
            const frameNumber = frames[0].ordinal;
            const time = times[frameNumber];
            if (time === undefined) throw new Error('Frame is outside the recording timeline');
            const seconds = Math.floor(time);
            const timecode = [Math.floor(seconds / 3600), Math.floor(seconds / 60) % 60, seconds % 60,
                Math.floor((time - seconds) * fps)].map(value => String(value).padStart(2, '0')).join(':');
            const timestamp = settingsRef.current.timestampFormat === 'timecode' ? timecode : `${time.toFixed(3)} s`;
            const labelText = `F${String(frameNumber).padStart(String(totalFrames).length, '0')}  |  ${timestamp}`;
            decoderGroup.videos.forEach(video => frameLabels.current.get(video.videoId)?.draw(labelText));
            presentedTime.current = time;
            displayedFrame = frameNumber;
            currentFrameRef.current = frameNumber;
            decoderGroup.setView(frameNumber, isPlaying ? decoderGroup.frameCapacity : 1, resolution);
            onFrameChangeRef.current?.(frameNumber);
            if (forceUi || performance.now() - lastUiUpdate >= 100) {
                setCurrentFrame(frameNumber); lastUiUpdate = performance.now();
            }
        };
        const run = async (): Promise<void> => {
            cameraRenderers = decoderGroup.videos.map(video => {
                const canvas = canvases.current.get(video.videoId);
                const renderer = canvas && renderers.current.get(canvas);
                if (!renderer) throw new Error(`Missing camera renderer for ${video.filename}`);
                return renderer;
            });
            const count = await decoderGroup.ready;
            if (!active) return;
            if (count !== totalFrames) throw new Error(`Video has ${count} frames but its recording timeline has ${totalFrames}`);
            const start = isPlaying ? currentFrameRef.current : requestedFrame;
            decoderGroup.setView(start, isPlaying ? decoderGroup.frameCapacity : 1, resolution);
            if (!isPlaying && decoderGroup.hasCached(start, PlaybackResolution.Preview)
                && !decoderGroup.hasCached(start, PlaybackResolution.Detail)) {
                const preview = await decoderGroup.read(start, PlaybackResolution.Preview, cameraRenderers);
                try {if (active) await present(preview, true);} finally {releaseGroupFrames(preview);}
                if (!active) return;
            }
            const first = await decoderGroup.read(start, resolution, cameraRenderers);
            try {
                if (!active) return;
                setError(null);
                await present(first, true);
                if (!active) return;
                setVideosReady(first.length);
                if (!isPlaying) return;
                const groupBytes = first.reduce((sum, frame) => sum + frame.image.width * frame.image.height * 4, 0);
                const presentationBytes = Math.min(MAX_PRESENTATION_BYTES, cacheBudgetBytes! / 4);
                const capacity = Math.min(Math.ceil(fps), Math.floor(presentationBytes / groupBytes) - 2);
                if (capacity < 1) throw new Error('Video group exceeds the playback buffer memory budget');
                buffer = new FrameLookahead({start: start + 1, end: totalFrames, capacity,
                    load: ordinal => decoderGroup.read(ordinal, resolution, cameraRenderers), release: releaseGroupFrames});
                await buffer.fill();
                if (!active) return;
                playbackClock.current = new PlaybackClock(start, performance.now(), fps * playbackRate);
                let waitingForImage = false;
                const tick = async (): Promise<void> => {
                    if (!active || !buffer || !playbackClock.current) return;
                    try {
                        if (waitingForImage && buffer.firstOrdinal !== undefined) {
                            playbackClock.current.resumeAt(buffer.firstOrdinal, performance.now());
                            waitingForImage = false;
                        }
                        const due = Math.min(totalFrames - 1, playbackClock.current.frameAt(performance.now()));
                        const frames = buffer.takeDue(due);
                        void buffer.fill().catch(fail);
                        if (!frames && buffer.size === 0 && !buffer.finished) waitingForImage = true;
                        if (frames) {
                            try {await present(frames, frames[0].ordinal === totalFrames - 1);}
                            finally {releaseGroupFrames(frames);}
                            if (!active) return;
                            playbackClock.current.presented(performance.now());
                        }
                        if (buffer.finished && currentFrameRef.current === totalFrames - 1) {
                            if (isLooping) {
                                buffer = new FrameLookahead({start: 0, end: totalFrames, capacity,
                                    load: ordinal => decoderGroup.read(ordinal, resolution, cameraRenderers), release: releaseGroupFrames});
                                await buffer.fill();
                                if (!active) return;
                                playbackClock.current = new PlaybackClock(0, performance.now(), fps * playbackRate);
                            } else {
                                requestedFrameRef.current = currentFrameRef.current;
                                setRequestedFrame(currentFrameRef.current); setIsPlaying(false); return;
                            }
                        }
                        if (active) timer = setTimeout(() => void tick(), Math.min(16, 1000 / (fps * playbackRate)));
                    } catch (failure) {fail(failure);}
                };
                timer = setTimeout(() => void tick(), 0);
            } finally {releaseGroupFrames(first);}
        };
        timer = setTimeout(() => void run().catch(fail), isPlaying ? 0 : 80);
        return () => {
            active = false; clearTimeout(timer);
            if (playbackClock.current) measuredFps.current = playbackClock.current.displayFps(performance.now());
            playbackClock.current = null;
            bitmapFrames.current = () => [];
            if (buffer) void buffer.close().catch(fail);
        };
    }, [decoderGroup, videoKey, requestedFrame, isPlaying, isLooping, playbackRate, leader, times, totalFrames, fps, cacheBudgetBytes]);

    useEffect(() => {
        if (isPlaying || !videosReady || !bundle || !recordingCache.current) return;
        let active = true;
        for (const [key, source] of Object.entries(bundle.videos.sources)) {
            const sourceType = Object.values(PlaybackSource).find(value => value === key);
            if (!sourceType || !source.valid || !source.videos.length) continue;
            const group = recordingCache.current.getGroup(source.videos, sourceType);
            if (group === decoderGroup) continue;
            group.setView(currentFrameRef.current, 1, PlaybackResolution.Detail);
            void group.prefetch(currentFrameRef.current, PlaybackResolution.Detail).catch(failure => {
                if (active) setError(`Could not prepare ${sourceType} at the paused frame: ${String(failure)}`);
            });
        }
        return () => {active = false;};
    }, [isPlaying, videosReady, currentFrame, decoderGroup, bundle]);
    const seek = useCallback((frame: number): void => {
        setIsPlaying(false);
        requestedFrameRef.current = Math.max(0, Math.min(Math.round(frame), totalFrames - 1));
        setRequestedFrame(requestedFrameRef.current);
    }, [totalFrames]);
    const setVideoRef = useCallback((id: string, canvas: HTMLCanvasElement | null): void => {
        if (canvas) {
            canvases.current.set(id, canvas);
            if (!renderers.current.has(canvas)) renderers.current.set(canvas, new ScheduledRenderer(canvas, failure => {
                setError(failure.message); setIsPlaying(false);
            }));
        } else {
            const detached = canvases.current.get(id);
            canvases.current.delete(id);
            // React can detach and reattach a ref within the same commit.
            queueMicrotask(() => {
                if (detached && ![...canvases.current.values()].includes(detached)) {
                    renderers.current.get(detached)?.close();
                    renderers.current.delete(detached);
                }
            });
        }
    }, []);
    const setFrameOverlayRef = useCallback((id: string, element: HTMLCanvasElement | null): void => {
        if (element) frameLabels.current.set(id, new PlaybackLabel(element)); else frameLabels.current.delete(id);
    }, []);
    const getDisplayFps = useCallback((): number | null => playbackClock.current?.displayFps(performance.now()) ?? measuredFps.current, []);
    const getRecordingTime = useCallback((): number | null => presentedTime.current, []);
    const setPlaybackRun = useCallback((run: PlaybackRun): void => {
        const saved = new Map(run.media.map(item => [JSON.stringify([item.video_source, item.video_filename]), item]));
        setMedia((bundle?.media ?? []).map(item => saved.get(JSON.stringify([item.video_source, item.video_filename])) ?? item));
    }, [bundle]);
    const cacheGroupRef = useRef(decoderGroup);
    cacheGroupRef.current = decoderGroup;
    const getCachedFrames = useCallback((): number[] => cacheGroupRef.current?.cachedOrdinals ?? [], []);
    const getBitmapFrames = useCallback((): number[] => bitmapFrames.current(), []);
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
        manifest, setPlaybackRun, reloadManifest, error, getRecordingTime, getCachedFrames, getBitmapFrames, getDisplayFps,
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
