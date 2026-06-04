import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { LoadedVideo } from '@/components/playback/RecordingBrowser';
import { serverUrls } from '@/services/server/server-helpers/server-urls';
import { backendFetch } from '@/services/electron-ipc/backend-fetch';

interface PlaybackState {
    loadedVideos: LoadedVideo[];
    recordingId: string | null;
    recordingPath: string | null;
    recordingFps: number | undefined;
    frameTimestamps: Record<string, number[]> | null;
    currentFrame: number;
}

let cachedPlaybackState: PlaybackState = {
    loadedVideos: [],
    recordingId: null,
    recordingPath: null,
    recordingFps: undefined,
    frameTimestamps: null,
    currentFrame: 0,
};

interface PlaybackContextValue extends PlaybackState {
    initialLoadPath: string | null;
    handleRecordingLoaded: (videos: LoadedVideo[], recId: string, path: string, fps?: number) => void;
    handleBack: () => void;
    handleFrameChange: (frame: number) => void;
}

const PlaybackContext = createContext<PlaybackContextValue | null>(null);

export const PlaybackContextProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const location = useLocation();
    const navigate = useNavigate();
    const locationState = location.state as { loadRecordingPath?: string } | null;
    const initialLoadPath = locationState?.loadRecordingPath ?? null;

    const initState =
        initialLoadPath && initialLoadPath !== cachedPlaybackState.recordingPath
            ? { loadedVideos: [] as LoadedVideo[], recordingId: null, recordingPath: null, recordingFps: undefined, frameTimestamps: null, currentFrame: 0 }
            : cachedPlaybackState;

    const [loadedVideos, setLoadedVideos] = useState<LoadedVideo[]>(initState.loadedVideos);
    const [recordingId, setRecordingId] = useState<string | null>(initState.recordingId);
    const [recordingPath, setRecordingPath] = useState<string | null>(initState.recordingPath);
    const [recordingFps, setRecordingFps] = useState<number | undefined>(initState.recordingFps);
    const [frameTimestamps, setFrameTimestamps] = useState<Record<string, number[]> | null>(initState.frameTimestamps);
    const [currentFrame] = useState<number>(initState.currentFrame);

    const handleRecordingLoaded = useCallback((videos: LoadedVideo[], recId: string, path: string, fps?: number) => {
        setLoadedVideos(videos);
        setRecordingId(recId);
        setRecordingPath(path);
        setRecordingFps(fps);
        setFrameTimestamps(null);
        cachedPlaybackState = { loadedVideos: videos, recordingId: recId, recordingPath: path, recordingFps: fps, frameTimestamps: null, currentFrame: 0 };
    }, []);

    useEffect(() => {
        if (loadedVideos.length === 0 || !recordingId) return;

        const fetchTimestamps = async () => {
            try {
                const response = await backendFetch(serverUrls.endpoints.playbackAllTimestamps(recordingId));
                if (!response.ok) return;
                const data = await response.json();
                if (data.timestamps && Object.keys(data.timestamps).length > 0) {
                    setFrameTimestamps(data.timestamps);
                    cachedPlaybackState.frameTimestamps = data.timestamps;
                }
            } catch {
                // Timestamps not available — SyncedVideoPlayer will use approximation
            }
        };
        fetchTimestamps();
    }, [loadedVideos, recordingId]);

    const handleBack = useCallback(() => {
        setLoadedVideos([]);
        setRecordingId(null);
        setRecordingPath(null);
        setRecordingFps(undefined);
        setFrameTimestamps(null);
        cachedPlaybackState = { loadedVideos: [], recordingId: null, recordingPath: null, recordingFps: undefined, frameTimestamps: null, currentFrame: 0 };
        navigate(location.pathname, { replace: true, state: {} });
    }, [navigate, location.pathname]);

    const handleFrameChange = useCallback((frame: number) => {
        cachedPlaybackState.currentFrame = frame;
    }, []);

    return (
        <PlaybackContext.Provider value={{
            loadedVideos,
            recordingId,
            recordingPath,
            recordingFps,
            frameTimestamps,
            currentFrame,
            initialLoadPath,
            handleRecordingLoaded,
            handleBack,
            handleFrameChange,
        }}>
            {children}
        </PlaybackContext.Provider>
    );
};

export const usePlaybackContext = (): PlaybackContextValue => {
    const ctx = useContext(PlaybackContext);
    if (!ctx) throw new Error('usePlaybackContext must be used within PlaybackContextProvider');
    return ctx;
};
