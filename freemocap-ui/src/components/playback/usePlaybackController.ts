import {BrowserVideo, type VideoEntry} from '@/services/recording/browser-video';
import {useCallback, useEffect, useRef, useState} from 'react';
import type {PlaybackSettings} from './SyncedVideoPlayer';
import {PlaybackLabel} from '@/services/recording/playback-label';
import type {PlaybackRun, PlaybackMedia} from '@/services/recording/playback-data';
import type {PlaybackBundle} from '@/store/slices/playback-data/playback-data-slice';

interface UsePlaybackControllerArgs {
    videos: VideoEntry[]; recordingId: string | null; recordingParentDirectory: string | null | undefined;
    bundle: Pick<PlaybackBundle, 'manifest' | 'media' | 'videos'> | null;
    reloadManifest: () => void;
    onFrameChange?: (frame: number) => void;
}

export function usePlaybackController({videos, recordingId, recordingParentDirectory, bundle, reloadManifest, onFrameChange}: UsePlaybackControllerArgs) {
    const [media, setMedia] = useState<PlaybackMedia[]>([]);
    const [error, setError] = useState<string | null>(null);
    const [isPlaying, setIsPlaying] = useState(false);
    const [currentFrame, setCurrentFrame] = useState(0);
    const [requestedFrame, setRequestedFrame] = useState(0);
    const [playbackRate, setPlaybackRate] = useState(1);
    const [isLooping, setIsLooping] = useState(false);
    const [videosReady, setVideosReady] = useState(0);
    const [erroredVideos, setErroredVideos] = useState(new Set<string>());
    const [settings, setSettings] = useState<PlaybackSettings>({showOverlays: true, timestampFormat: 'seconds'});
    const settingsRef = useRef(settings); settingsRef.current = settings;
    const elements = useRef(new Map<string, HTMLVideoElement>());
    const [elementRevision, setElementRevision] = useState(0);
    const players = useRef<BrowserVideo[]>([]);
    const frameLabels = useRef(new Map<string, PlaybackLabel>());
    const currentFrameRef = useRef(0);
    const measuredFps = useRef<number | null>(null);
    const seekGeneration = useRef(0);
    const onFrameChangeRef = useRef(onFrameChange); onFrameChangeRef.current = onFrameChange;
    const videosRef = useRef(videos); videosRef.current = videos;
    const source = Object.entries(bundle?.videos.sources ?? {}).find(([, value]) => value.videos.some(video => video.streamUrl === videos[0]?.streamUrl));
    const leader = media.find(item => item.video_source === source?.[0] && item.video_filename === videos[0]?.filename);
    const totalFrames = leader?.timeline.frame_numbers.length ?? 0;
    const fps = leader?.nominal_fps ?? 30;
    const duration = totalFrames / fps;
    const videoKey = JSON.stringify(videos);
    const fail = useCallback((failure: Error): void => {setError(failure.message); setIsPlaying(false);}, []);
    useEffect(() => {setMedia(bundle?.media ?? []);}, [bundle]);
    useEffect(() => {
        currentFrameRef.current = 0; setCurrentFrame(0); setRequestedFrame(0); setIsPlaying(false);
    }, [recordingId, recordingParentDirectory]);

    useEffect(() => {
        setIsPlaying(false); setVideosReady(0); setError(null); setErroredVideos(new Set());
        setRequestedFrame(currentFrameRef.current);
        if (!totalFrames || !videosRef.current.length) return;
        if (source && !source[1].valid) {fail(new Error('Video group has incompatible frame counts. See recording resource errors.')); return;}
        if (videosRef.current.some(video => !elements.current.has(video.videoId))) return;
        let active = true;
        const opened = videosRef.current.map(video => {
            const element = elements.current.get(video.videoId);
            if (!element) throw new Error(`Missing video element: ${video.filename}`);
            return new BrowserVideo(element, video.streamUrl, duration, fail);
        });
        players.current = opened;
        const start = currentFrameRef.current / fps;
        void Promise.allSettled(opened.map(player => player.open(start))).then(results => {
            if (!active) return;
            const failed = new Set<string>();
            const failures: string[] = [];
            players.current = opened.filter((player, index) => {
                const result = results[index];
                if (result.status === 'fulfilled') return true;
                failed.add(videosRef.current[index].videoId);
                failures.push(`${videosRef.current[index].filename}: ${String(result.reason)}`);
                player.close(); return false;
            });
            setErroredVideos(failed); setVideosReady(players.current.length);
            if (failures.length) setError(failures.join('\n'));
        });
        return () => {active = false; opened.forEach(player => player.close()); players.current = [];};
    }, [videoKey, totalFrames, duration, fps, recordingId, recordingParentDirectory, elementRevision, fail]);

    const seek = useCallback(async (frame: number): Promise<void> => {
        const generation = ++seekGeneration.current;
        setIsPlaying(false);
        const target = Math.max(0, Math.min(Math.round(frame), totalFrames - 1));
        currentFrameRef.current = target; setRequestedFrame(target); setCurrentFrame(target);
        onFrameChangeRef.current?.(target);
        const current = players.current;
        current.forEach(player => player.element.pause());
        await Promise.all(current.map(player => player.seek(target / fps))).catch(failure => {
            if (players.current === current && generation === seekGeneration.current) fail(failure);
        });
    }, [fps, totalFrames, fail]);

    useEffect(() => {
        const current = players.current;
        current.forEach(player => {player.element.playbackRate = playbackRate;});
        if (isPlaying) {
            measuredFps.current = null;
            void Promise.all(current.map(player => player.element.play())).catch(failure => {if (players.current === current) fail(failure);});
        } else current.forEach(player => player.element.pause());
    }, [isPlaying, playbackRate, videosReady, fail]);

    useEffect(() => {
        const leaderElement = players.current[0]?.element;
        if (!leaderElement || !videosReady) return;
        let handle = 0;
        let lastUi = 0;
        let startTime = performance.now();
        let count = 0;
        const tick = (now: number, metadata: VideoFrameCallbackMetadata): void => {
            const frame = isPlaying ? Math.min(totalFrames - 1, Math.max(0, Math.round(metadata.mediaTime * fps))) : currentFrameRef.current;
            currentFrameRef.current = frame;
            onFrameChangeRef.current?.(frame);
            const seconds = Math.floor(metadata.mediaTime);
            const timecode = [Math.floor(seconds / 3600), Math.floor(seconds / 60) % 60, seconds % 60,
                Math.floor((metadata.mediaTime - seconds) * fps)].map(value => String(value).padStart(2, '0')).join(':');
            const timestamp = settingsRef.current.timestampFormat === 'timecode' ? timecode : `${metadata.mediaTime.toFixed(3)} s`;
            frameLabels.current.forEach(label => label.draw(`~F${frame} | ${timestamp}`));
            if (isPlaying) {
                count++;
                if (now - startTime >= 500) {measuredFps.current = count * 1000 / (now - startTime); count = 0; startTime = now;}
            }
            if (now - lastUi >= 100) {setCurrentFrame(frame); lastUi = now;}
            handle = leaderElement.requestVideoFrameCallback(tick);
        };
        const ended = (): void => {void seek(isLooping ? 0 : totalFrames - 1).then(() => {if (isLooping) setIsPlaying(true);});};
        leaderElement.addEventListener('ended', ended);
        handle = leaderElement.requestVideoFrameCallback(tick);
        return () => {leaderElement.cancelVideoFrameCallback(handle); leaderElement.removeEventListener('ended', ended);};
    }, [videosReady, isPlaying, isLooping, fps, totalFrames, seek]);

    const setVideoRef = useCallback((id: string, element: HTMLVideoElement | null): void => {
        if ((elements.current.get(id) ?? null) === element) return;
        if (element) elements.current.set(id, element); else elements.current.delete(id);
        setElementRevision(revision => revision + 1);
    }, []);
    const setFrameOverlayRef = useCallback((id: string, element: HTMLCanvasElement | null): void => {
        if (element) frameLabels.current.set(id, new PlaybackLabel(element)); else frameLabels.current.delete(id);
    }, []);
    const getDisplayFps = useCallback(() => measuredFps.current, []);
    const getRecordingTime = useCallback(() => leader?.timeline.timestamps_s[currentFrameRef.current] ?? null, [leader]);
    const setPlaybackRun = useCallback((run: PlaybackRun): void => {
        const saved = new Map(run.media.map(item => [JSON.stringify([item.video_source, item.video_filename]), item]));
        setMedia((bundle?.media ?? []).map(item => saved.get(JSON.stringify([item.video_source, item.video_filename])) ?? item));
    }, [bundle]);
    const getCachedFrames = useCallback((): number[] => {
        const ranges = players.current[0]?.element.buffered;
        if (!ranges) return [];
        const frames: number[] = [];
        for (let i = 0; i < ranges.length; i++) for (let n = Math.ceil(ranges.start(i) * fps); n < Math.min(totalFrames, ranges.end(i) * fps); n++) frames.push(n);
        return frames;
    }, [fps, totalFrames]);
    const handlePlayPause = useCallback((): void => {
        if (isPlaying) setRequestedFrame(currentFrameRef.current);
        else if (currentFrameRef.current >= totalFrames - 1) {void seek(0).then(() => setIsPlaying(true)); return;}
        setIsPlaying(value => !value);
    }, [isPlaying, totalFrames, seek]);
    useEffect(() => {
        const onKey = (event: KeyboardEvent): void => {
            if (event.target instanceof HTMLElement && (event.target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT', 'BUTTON'].includes(event.target.tagName))) return;
            switch (event.key) {
                case ' ': event.preventDefault(); handlePlayPause(); break;
                case 'ArrowLeft': event.preventDefault(); seek(currentFrameRef.current - 1); break;
                case 'ArrowRight': event.preventDefault(); seek(currentFrameRef.current + 1); break;
                case 'Home': event.preventDefault(); seek(0); break;
                case 'End': event.preventDefault(); seek(totalFrames - 1); break;
            }
        };
        window.addEventListener('keydown', onKey); return () => window.removeEventListener('keydown', onKey);
    }, [handlePlayPause, seek]);
    return {
        manifest: bundle?.manifest ?? null, setPlaybackRun, reloadManifest, error, getRecordingTime, getCachedFrames, getDisplayFps,
        seekFrame: isPlaying ? currentFrame : requestedFrame,
        isPlaying, currentFrame, totalFrames, duration, playbackRate, fps, currentTime: currentFrame / fps, settings,
        isLooping, videosReady, allReady: videosReady > 0 && videosReady + erroredVideos.size === videos.length,
        erroredVideos, setSettings, handlePlayPause, isSeeking: false,
        handleSeekDrag: seek, handleSeekCommit: seek,
        handleFrameStep: (delta: number): void => {void seek(currentFrameRef.current + delta);},
        handlePlaybackRateChange: setPlaybackRate,
        handleSeekToStart: (): void => {void seek(0);}, handleSeekToEnd: (): void => {void seek(totalFrames - 1);},
        handleToggleLoop: (): void => setIsLooping(value => !value),
        setVideoRef, setFrameOverlayRef, currentFrameRef,
    };
}
export type PlaybackController = ReturnType<typeof usePlaybackController>;
