import React, {createContext, useCallback, useContext, useEffect, useRef, useState} from 'react';
import type {LoadedVideo} from './RecordingBrowser';
import {useAppDispatch, useAppSelector} from '@/store';
import {
    activeRecordingSet,
    selectActiveRecordingBaseDirectory,
    selectActiveRecordingName,
    selectActiveRecordingOrigin,
    splitParentAndName,
} from '@/store/slices/active-recording/active-recording-slice';
import {selectRecordingsList} from '@/store/slices/recording-status/recording-status-slice';
import {fetchPlaybackBundle, selectPlaybackBundle} from '@/store/slices/playback-data/playback-data-slice';

export interface SourceInfo {
    available: boolean;
    valid: boolean;
    video_count: number;
    videos: LoadedVideo[];
}

interface PlaybackContextValue {
    loadedVideos: LoadedVideo[];
    recordingFps: number | undefined;
    cachedCurrentFrame: number;
    availableSources: Record<string, SourceInfo> | null;
    selectedSource: string | null;
    setSelectedSource: (source: string) => void;
    onRecordingLoaded: (
        videos: LoadedVideo[],
        recordingPath: string,
        recordingFps?: number,
        sources?: Record<string, SourceInfo>,
        preferred?: string,
    ) => void;
    onFrameChange: (frame: number) => void;
}

const PlaybackContext = createContext<PlaybackContextValue | null>(null);

export const PlaybackProvider: React.FC<{ children: React.ReactNode }> = ({children}) => {
    const dispatch = useAppDispatch();
    const activeRecordingOrigin = useAppSelector(selectActiveRecordingOrigin);
    const activeRecordingName = useAppSelector(selectActiveRecordingName);
    const activeRecordingBaseDirectory = useAppSelector(selectActiveRecordingBaseDirectory);

    const [loadedVideos, setLoadedVideos] = useState<LoadedVideo[]>([]);
    const [recordingFps, setRecordingFps] = useState<number | undefined>(undefined);
    const [availableSources, setAvailableSources] = useState<Record<string, SourceInfo> | null>(null);
    const [selectedSource, setSelectedSource] = useState<string | null>(null);
    const currentFrameRef = useRef<number>(0);
    const appliedBundle = useRef<unknown>(null);
    const appliedLocation = useRef<string | null>(null);

    const onRecordingLoaded = useCallback((
        videos: LoadedVideo[],
        path: string,
        fps?: number,
        sources?: Record<string, SourceInfo>,
        preferred?: string,
    ) => {
        setLoadedVideos(videos);
        setRecordingFps(fps);
        setAvailableSources(sources ?? null);
        setSelectedSource(preferred ?? (sources ? Object.keys(sources)[0] ?? null : null));
        currentFrameRef.current = 0;
    }, []);

    const onFrameChange = useCallback((frame: number) => {
        currentFrameRef.current = frame;
    }, []);

    useEffect(() => {
        if (!activeRecordingName || activeRecordingOrigin === 'pending-capture') return;
        setLoadedVideos([]);
        void dispatch(fetchPlaybackBundle({recordingId: activeRecordingName, recordingParentDirectory: activeRecordingBaseDirectory}));
    }, [activeRecordingName, activeRecordingBaseDirectory, activeRecordingOrigin, dispatch]);

    const bundle = useAppSelector(selectPlaybackBundle(activeRecordingName, activeRecordingBaseDirectory));

    useEffect(() => {
        if (!bundle || activeRecordingOrigin === 'pending-capture') return;
        if (bundle === appliedBundle.current) return;
        const location = JSON.stringify([activeRecordingBaseDirectory, activeRecordingName]);
        const sameRecording = location === appliedLocation.current;
        appliedBundle.current = bundle;
        appliedLocation.current = location;

        const sources: Record<string, SourceInfo> = {};
        for (const [key, source] of Object.entries(bundle.videos.sources)) {
            sources[key] = {
                available: source.available,
                valid: source.valid,
                video_count: source.videoCount,
                videos: source.videos,
            };
        }
        const preferred = sameRecording && selectedSource && sources[selectedSource]?.valid
            ? selectedSource : bundle.videos.preferredSource;
        const preferredVids = sources[preferred]?.videos ?? [];

        setLoadedVideos(preferredVids);
        setRecordingFps(bundle.recordingFps ?? undefined);
        setAvailableSources(sources);
        setSelectedSource(preferred);
        if (!sameRecording) currentFrameRef.current = 0;
    }, [bundle, activeRecordingOrigin, activeRecordingName, activeRecordingBaseDirectory, selectedSource]);

    // When selectedSource changes, swap loadedVideos to the new source's pre-fetched list.
    useEffect(() => {
        if (!selectedSource || !availableSources) return;
        const source = availableSources[selectedSource];
        if (!source?.videos.length) return;
        setLoadedVideos(source.videos);
    }, [selectedSource, availableSources]);

    // Bootstrap: if no active recording on mount, auto-pick the most recent from cache.
    const recordingsList = useAppSelector(selectRecordingsList);

    useEffect(() => {
        if (activeRecordingName) return;
        if (activeRecordingOrigin === 'pending-capture') return;
        if (recordingsList.length === 0) return;

        const latest = recordingsList[0];
        const parsed = splitParentAndName(latest.path);
        setRecordingFps(latest.fps ?? undefined);
        dispatch(activeRecordingSet({
            recordingName: latest.name,
            origin: 'auto-latest',
            baseDirectory: parsed?.baseDirectory,
        }));
    }, [activeRecordingName, activeRecordingOrigin, recordingsList, dispatch]);

    return (
        <PlaybackContext.Provider value={{
            loadedVideos,
            recordingFps,
            cachedCurrentFrame: currentFrameRef.current,
            availableSources,
            selectedSource,
            setSelectedSource,
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
