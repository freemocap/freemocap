import React, {createContext, useCallback, useContext, useEffect, useRef, useState} from 'react';
import type {LoadedVideo} from './RecordingBrowser';
import {serverUrls} from '@/constants/server-urls';
import {useAppDispatch, useAppSelector} from '@/store';
import {
    activeRecordingSet,
    selectActiveRecordingName,
    selectActiveRecordingOrigin,
} from '@/store/slices/active-recording/active-recording-slice';

interface PlaybackContextValue {
    loadedVideos: LoadedVideo[];
    recordingFps: number | undefined;
    frameTimestamps: Record<string, number[]> | null;
    cachedCurrentFrame: number;
    onRecordingLoaded: (videos: LoadedVideo[], recordingPath: string, recordingFps?: number) => void;
    onFrameChange: (frame: number) => void;
}

const PlaybackContext = createContext<PlaybackContextValue | null>(null);

export const PlaybackProvider: React.FC<{ children: React.ReactNode }> = ({children}) => {
    const dispatch = useAppDispatch();
    const activeRecordingOrigin = useAppSelector(selectActiveRecordingOrigin);
    const activeRecordingName = useAppSelector(selectActiveRecordingName);

    const [loadedVideos, setLoadedVideos] = useState<LoadedVideo[]>([]);
    const [loadedRecordingName, setLoadedRecordingName] = useState<string | null>(null);
    const [recordingFps, setRecordingFps] = useState<number | undefined>(undefined);
    const [frameTimestamps, setFrameTimestamps] = useState<Record<string, number[]> | null>(null);
    const currentFrameRef = useRef<number>(0);

    const onRecordingLoaded = useCallback((videos: LoadedVideo[], path: string, fps?: number) => {
        setLoadedVideos(videos);
        setLoadedRecordingName(path);
        setRecordingFps(fps);
        setFrameTimestamps(null);
        currentFrameRef.current = 0;
    }, []);

    const onFrameChange = useCallback((frame: number) => {
        currentFrameRef.current = frame;
    }, []);

    // Fetch per-camera timestamps for the loaded recording.
    useEffect(() => {
        if (loadedVideos.length === 0 || !loadedRecordingName) return;
        let cancelled = false;
        (async () => {
            try {
                const response = await fetch(serverUrls.endpoints.playbackAllTimestamps(loadedRecordingName));
                if (!response.ok || cancelled) return;
                const data = await response.json();
                if (!cancelled && data.timestamps && Object.keys(data.timestamps).length > 0) {
                    setFrameTimestamps(data.timestamps);
                }
            } catch {
                // Timestamps not available
            }
        })();
        return () => { cancelled = true; };
    }, [loadedVideos, loadedRecordingName]);

    // When the active recording changes (and videos haven't been loaded for it yet),
    // fetch its video list. Skip if user is staging a pending capture.
    useEffect(() => {
        if (!activeRecordingName) return;
        if (activeRecordingOrigin === 'pending-capture') return;
        if (activeRecordingName === loadedRecordingName) return;

        let cancelled = false;
        (async () => {
            try {
                const vidResp = await fetch(serverUrls.endpoints.playbackVideos(activeRecordingName));
                if (!vidResp.ok || cancelled) return;
                const vidsData = await vidResp.json();
                const baseUrl = serverUrls.getHttpUrl();
                const vids: LoadedVideo[] = vidsData.map((v: any) => ({
                    videoId: v.video_id,
                    filename: v.filename,
                    streamUrl: `${baseUrl}${v.stream_url}`,
                    sizeBytes: v.size_bytes,
                }));
                if (!cancelled) {
                    onRecordingLoaded(vids, activeRecordingName);
                }
            } catch {
                // Ignore errors
            }
        })();
        return () => { cancelled = true; };
    }, [activeRecordingName, activeRecordingOrigin, loadedRecordingName, onRecordingLoaded]);

    // Bootstrap: if no active recording on mount, auto-pick the most recent on disk.
    useEffect(() => {
        if (activeRecordingName) return;
        if (activeRecordingOrigin === 'pending-capture') return;

        let cancelled = false;
        (async () => {
            try {
                const response = await fetch(serverUrls.endpoints.playbackRecordings);
                if (!response.ok || cancelled) return;
                const data = await response.json();
                if (cancelled || !data || data.length === 0) return;
                const latest = data[0];
                setRecordingFps(latest.fps);
                dispatch(activeRecordingSet({
                    recordingName: latest.name,
                    origin: 'auto-latest',
                }));
            } catch {
                // Ignore errors
            }
        })();
        return () => { cancelled = true; };
    }, [activeRecordingName, activeRecordingOrigin, dispatch]);

    return (
        <PlaybackContext.Provider value={{
            loadedVideos,
            recordingFps,
            frameTimestamps,
            cachedCurrentFrame: currentFrameRef.current,
            onRecordingLoaded,
            onFrameChange,
        }}>
            {children}
        </PlaybackContext.Provider>
    );
};

export function usePlaybackContext(): PlaybackContextValue | null {
    return useContext(PlaybackContext);
}
