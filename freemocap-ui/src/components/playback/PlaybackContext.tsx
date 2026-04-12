import React, {createContext, useCallback, useContext, useEffect, useState} from 'react';
import type {LoadedVideo} from './RecordingBrowser';
import {serverUrls} from '@/constants/server-urls';

// Module-level cache so playback state survives tab switches
let cachedPlaybackState = {
    loadedVideos: [] as LoadedVideo[],
    recordingPath: null as string | null,
    recordingFps: undefined as number | undefined,
    frameTimestamps: null as Record<string, number[]> | null,
    currentFrame: 0,
};

interface PlaybackContextValue {
    loadedVideos: LoadedVideo[];
    recordingPath: string | null;
    recordingFps: number | undefined;
    frameTimestamps: Record<string, number[]> | null;
    initialLoadPath: string | null;
    cachedCurrentFrame: number;
    onRecordingLoaded: (videos: LoadedVideo[], recordingPath: string, recordingFps?: number) => void;
    onFrameChange: (frame: number) => void;
    setInitialLoadPath: (path: string | null) => void;
}

const PlaybackContext = createContext<PlaybackContextValue | null>(null);

export const PlaybackProvider: React.FC<{ children: React.ReactNode }> = ({children}) => {
    const [initialLoadPath, setInitialLoadPath] = useState<string | null>(null);

    const initState = (initialLoadPath && initialLoadPath !== cachedPlaybackState.recordingPath)
        ? {
            loadedVideos: [] as LoadedVideo[],
            recordingPath: null,
            recordingFps: undefined,
            frameTimestamps: null,
            currentFrame: 0,
        }
        : cachedPlaybackState;

    const [loadedVideos, setLoadedVideos] = useState<LoadedVideo[]>(initState.loadedVideos);
    const [recordingPath, setRecordingPath] = useState<string | null>(initState.recordingPath);
    const [recordingFps, setRecordingFps] = useState<number | undefined>(initState.recordingFps);
    const [frameTimestamps, setFrameTimestamps] = useState<Record<string, number[]> | null>(initState.frameTimestamps);

    const onRecordingLoaded = useCallback((videos: LoadedVideo[], path: string, fps?: number) => {
        setLoadedVideos(videos);
        setRecordingPath(path);
        setRecordingFps(fps);
        setFrameTimestamps(null);
        cachedPlaybackState = {
            loadedVideos: videos,
            recordingPath: path,
            recordingFps: fps,
            frameTimestamps: null,
            currentFrame: 0,
        };
    }, []);

    const onFrameChange = useCallback((frame: number) => {
        cachedPlaybackState.currentFrame = frame;
    }, []);

    // After a recording is loaded, fetch real timestamps from the server
    useEffect(() => {
        if (loadedVideos.length === 0) return;
        const fetchTimestamps = async () => {
            try {
                if (recordingPath) {
                    const response = await fetch(serverUrls.endpoints.playbackAllTimestamps(recordingPath));
                    if (!response.ok) return;
                    const data = await response.json();
                    if (data.timestamps && Object.keys(data.timestamps).length > 0) {
                        setFrameTimestamps(data.timestamps);
                        cachedPlaybackState.frameTimestamps = data.timestamps;
                    }
                }
            } catch {
                // Timestamps not available
            }
        };
        fetchTimestamps();
    }, [loadedVideos, recordingPath]);

    // Auto-load latest recording on mount if nothing is loaded
    useEffect(() => {
        if (initialLoadPath || initState.loadedVideos.length > 0) return;

        let isMounted = true;
        const fetchLatest = async () => {
            try {
                const response = await fetch(serverUrls.endpoints.playbackRecordings);
                if (response.ok && isMounted) {
                    const data = await response.json();
                    if (data && data.length > 0) {
                        const latest = data[0];
                        const vidResp = await fetch(serverUrls.endpoints.playbackVideos(latest.name));
                        if (vidResp.ok && isMounted) {
                            const vidsData = await vidResp.json();
                            const baseUrl = serverUrls.getHttpUrl();
                            const vids = vidsData.map((v: any) => ({
                                videoId: v.video_id,
                                filename: v.filename,
                                streamUrl: `${baseUrl}${v.stream_url}`,
                                sizeBytes: v.size_bytes,
                            }));
                            onRecordingLoaded(vids, latest.name, latest.fps);
                        }
                    }
                }
            } catch {
                // Ignore errors
            }
        };
        fetchLatest();
        return () => { isMounted = false; };
    }, [initialLoadPath, initState.loadedVideos.length]);

    return (
        <PlaybackContext.Provider value={{
            loadedVideos,
            recordingPath,
            recordingFps,
            frameTimestamps,
            initialLoadPath,
            cachedCurrentFrame: initState.currentFrame,
            onRecordingLoaded,
            onFrameChange,
            setInitialLoadPath,
        }}>
            {children}
        </PlaybackContext.Provider>
    );
};

export function usePlaybackContext(): PlaybackContextValue | null {
    return useContext(PlaybackContext);
}
