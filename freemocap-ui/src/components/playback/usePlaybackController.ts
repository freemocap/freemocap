import {useCallback, useEffect, useRef, useState} from 'react';
import type {PlaybackSettings} from './SyncedVideoPlayer';
import {mediaFrameAtRecordingTime, type MediaPosition} from '@/services/recording/playback-timing';
import {type PlaybackManifest, type PlaybackRun, type PlaybackMedia} from '@/services/recording/playback-data';
import {serverUrls} from '@/constants/server-urls';

interface VideoEntry {videoId: string; filename: string; streamUrl: string}
interface UsePlaybackControllerArgs {
    videos: VideoEntry[]; recordingId: string | null; recordingParentDirectory: string | null | undefined;
    onFrameChange?: (frame: number) => void;
}

export function usePlaybackController({videos, recordingId, recordingParentDirectory, onFrameChange}: UsePlaybackControllerArgs) {
    const [manifest, setManifest] = useState<PlaybackManifest | null>(null);
    const [media, setMedia] = useState<PlaybackMedia[]>([]);
    const [reload, setReload] = useState(0);
    const [error, setError] = useState<string | null>(null);
    const [isPlaying, setIsPlaying] = useState(false);
    const [currentFrame, setCurrentFrame] = useState(0);
    const [requestedFrame, setRequestedFrame] = useState(0);
    const [playbackRate, setPlaybackRate] = useState(1);
    const [isLooping, setIsLooping] = useState(false);
    const [videosReady, setVideosReady] = useState(0);
    const [settings, setSettings] = useState<PlaybackSettings>({showOverlays: true, timestampFormat: 'seconds'});
    const canvases = useRef(new Map<string, HTMLCanvasElement>());
    const frameLabels = useRef(new Map<string, HTMLElement>());
    const timeLabels = useRef(new Map<string, HTMLElement>());
    const presentedMedia = useRef<MediaPosition | null>(null);
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
    const parameters = new URLSearchParams();
    if (recordingParentDirectory) parameters.set('recording_parent_directory', recordingParentDirectory);
    const manifestUrl = recordingId ? `${serverUrls.getHttpUrl()}/freemocap/playback/${encodeURIComponent(recordingId)}/manifest?${parameters}` : null;

    useEffect(() => {
        const abort = new AbortController();
        setManifest(null); setMedia([]); setError(null); setIsPlaying(false);
        setVideosReady(0); setCurrentFrame(0); setRequestedFrame(0); presentedMedia.current = null;
        if (!manifestUrl) return;
        void (async () => {
            try {
                const response = await fetch(manifestUrl, {signal: abort.signal});
                if (response.status === 404) {
                    const url = new URL(manifestUrl);
                    url.pathname = url.pathname.replace(/\/manifest$/, '/media');
                    const mediaResponse = await fetch(url, {signal: abort.signal});
                    if (!mediaResponse.ok) throw new Error(await mediaResponse.text());
                    const result: PlaybackMedia[] = await mediaResponse.json();
                    if (!abort.signal.aborted) setMedia(result);
                    return;
                }
                if (!response.ok) throw new Error(await response.text());
                const result: PlaybackManifest = await response.json();
                if (abort.signal.aborted) return;
                const selected = result.runs.find(item => item.run_id === result.selected_run_id);
                if (!selected) throw new Error('Selected recording result is missing');
                setManifest(result); setMedia(selected.media);
            } catch (failure) {if (!abort.signal.aborted) setError(String(failure));}
        })();
        return () => abort.abort();
    }, [manifestUrl, reload]);

    useEffect(() => {
        setIsPlaying(false); setCurrentFrame(0); setRequestedFrame(0); setVideosReady(0);
        presentedMedia.current = null;
        canvases.current.forEach(canvas => canvas.getContext('2d')?.clearRect(0, 0, canvas.width, canvas.height));
    }, [media, videoKey]);

    useEffect(() => {
        if (!media.length || !videosRef.current.length) return;
        const abort = new AbortController();
        setError(null);
        let timer: ReturnType<typeof setTimeout> | undefined;
        const loadFrames = async (): Promise<void> => {
            const bitmaps: ImageBitmap[] = [];
            const started = performance.now();
            try {
                if (!leader || !times) throw new Error('The selected video has no saved timing binding');
                const time = times[requestedFrame];
                if (time === undefined) throw new Error('Requested frame is outside the selected timeline');
                const frames = videosRef.current.map(video => {
                    const bindings = media.filter(item => item.video_filename === video.filename);
                    if (bindings.length !== 1) throw new Error(`Expected one timing binding for ${video.filename}`);
                    return {video, frame: mediaFrameAtRecordingTime(bindings[0], time)};
                });
                const results = await Promise.allSettled(frames.map(async ({video, frame}) => {
                    if (frame === null) return null;
                    const url = new URL(video.streamUrl);
                    url.pathname += `/frames/${frame}`;
                    const response = await fetch(url, {signal: abort.signal});
                    if (!response.ok) throw new Error(await response.text());
                    const bitmap = await createImageBitmap(await response.blob());
                    bitmaps.push(bitmap);
                    return bitmap;
                }));
                if (abort.signal.aborted) return;
                const failure = results.find(result => result.status === 'rejected');
                if (failure?.status === 'rejected') throw failure.reason;
                const targets = frames.map(({video}) => {
                    const canvas = canvases.current.get(video.videoId);
                    if (!canvas) throw new Error(`Missing playback canvas for ${video.filename}`);
                    const context = canvas.getContext('2d');
                    if (!context) throw new Error('Canvas rendering is unavailable');
                    return {canvas, context};
                });
                // Present only after every camera image and destination is ready.
                frames.forEach(({video, frame}, index) => {
                    const {canvas, context} = targets[index];
                    const result = results[index];
                    const bitmap = result.status === 'fulfilled' ? result.value : null;
                    if (bitmap) {
                        canvas.width = bitmap.width; canvas.height = bitmap.height;
                        context.drawImage(bitmap, 0, 0);
                    } else {context.clearRect(0, 0, canvas.width, canvas.height);}
                    const label = frameLabels.current.get(video.videoId);
                    if (label) label.textContent = frame === null ? 'No sample' : `F${frame}`;
                    const timeLabel = timeLabels.current.get(video.videoId);
                    if (timeLabel) timeLabel.textContent = `${time.toFixed(3)} s`;
                });
                presentedMedia.current = {filename: leader.video_filename,
                    time_s: leader.timeline.frame_numbers[requestedFrame] / leader.nominal_fps};
                currentFrameRef.current = requestedFrame;
                setCurrentFrame(requestedFrame); setVideosReady(frames.length);
                onFrameChangeRef.current?.(requestedFrame);
                if (isPlaying) {
                    const next = requestedFrame + 1;
                    if (times.length === 1 || (next >= times.length && !isLooping)) {setIsPlaying(false); return;}
                    const interval = next < times.length ? times[next] - time : 1 / leader.nominal_fps;
                    timer = setTimeout(() => setRequestedFrame(next < times.length ? next : 0),
                        Math.max(0, interval * 1000 / playbackRate - (performance.now() - started)));
                }
            } catch (failure) {
                if (!abort.signal.aborted) {setError(String(failure)); setIsPlaying(false);}
            } finally {bitmaps.forEach(bitmap => bitmap.close());}
        };
        const startTimer = setTimeout(() => void loadFrames(), isPlaying ? 0 : 80);
        return () => {abort.abort(); clearTimeout(startTimer); if (timer !== undefined) clearTimeout(timer);};
    }, [media, videoKey, requestedFrame, isPlaying, isLooping, playbackRate, leader, times]);

    const seek = useCallback((frame: number): void => {
        setIsPlaying(false);
        setRequestedFrame(Math.max(0, Math.min(Math.round(frame), totalFrames - 1)));
    }, [totalFrames]);
    const setVideoRef = useCallback((id: string, canvas: HTMLCanvasElement | null): void => {
        if (canvas) canvases.current.set(id, canvas); else canvases.current.delete(id);
    }, []);
    const setFrameOverlayRef = useCallback((id: string, element: HTMLElement | null): void => {
        if (element) frameLabels.current.set(id, element); else frameLabels.current.delete(id);
    }, []);
    const setTimeOverlayRef = useCallback((id: string, element: HTMLElement | null): void => {
        if (element) timeLabels.current.set(id, element); else timeLabels.current.delete(id);
    }, []);
    const getMediaPosition = useCallback((): MediaPosition | null => presentedMedia.current, []);
    const reloadManifest = useCallback((): void => setReload(value => value + 1), []);
    const setPlaybackRun = useCallback((run: PlaybackRun): void => setMedia(run.media), []);
    const handlePlayPause = useCallback((): void => {
        if (currentFrame >= totalFrames - 1) setRequestedFrame(0);
        setIsPlaying(value => !value);
    }, [currentFrame, totalFrames]);
    useEffect(() => {
        const onKey = (event: KeyboardEvent): void => {
            const element = event.target;
            if (element instanceof HTMLElement && (element.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT', 'BUTTON'].includes(element.tagName))) return;
            switch (event.key) {
                case ' ': event.preventDefault(); handlePlayPause(); break;
                case 'ArrowLeft': event.preventDefault(); seek(currentFrame - 1); break;
                case 'ArrowRight': event.preventDefault(); seek(currentFrame + 1); break;
                case 'Home': event.preventDefault(); seek(0); break;
                case 'End': event.preventDefault(); seek(totalFrames - 1); break;
            }
        };
        window.addEventListener('keydown', onKey);
        return () => window.removeEventListener('keydown', onKey);
    }, [handlePlayPause, seek, currentFrame, totalFrames]);
    return {
        manifest, setPlaybackRun, reloadManifest, error, getMediaPosition,
        isPlaying, currentFrame, totalFrames, duration, playbackRate, fps, currentTime, settings,
        isLooping, videosReady, allReady: videosReady === videos.length && videos.length > 0,
        erroredVideos: new Set<string>(), setSettings,
        handlePlayPause, isSeeking: requestedFrame !== currentFrame,
        handleSeekDrag: seek, handleSeekCommit: seek,
        handleFrameStep: (delta: number): void => seek(currentFrame + delta),
        handlePlaybackRateChange: setPlaybackRate,
        handleSeekToStart: (): void => seek(0), handleSeekToEnd: (): void => seek(totalFrames - 1),
        handleToggleLoop: (): void => setIsLooping(value => !value),
        setVideoRef, setFrameOverlayRef, setTimeOverlayRef,
        frameTimestampsRef, currentFrameRef,
    };
}

export type PlaybackController = ReturnType<typeof usePlaybackController>;
