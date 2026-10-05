import {useEffect, useMemo, useRef, useState, type ReactNode} from 'react';
import {serverUrls} from '@/constants/server-urls';
import {KeypointsSourceProvider, type KeypointsSource, type KeypointsFrame, type KeypointsCallback, type ModelsCallback, type ModelFramesCallback} from './KeypointsSourceContext';
import type {ModelDefinition} from '@/services/server/transport/message-contract';
import type {ResolvedModelFrame} from '@/services/server/transport/frame-types';
import {recordedKeypoints, recordedModelFrame, RecordingChannelKind, type PlaybackManifest, type PlaybackChannelData, type PlaybackRun} from '@/services/recording/playback-data';

import {PlaybackLoadResultSchema} from '@/services/recording/playback-parquet-messages';
import {fittedSkeletonFrames} from '@/services/recording/fitted-skeleton';
import type {FittedSkeletonDefinition, FittedSkeletonFrame} from '@/services/recording/fitted-skeleton-types';

interface PlaybackState {models: ModelDefinition[]; frames: ResolvedModelFrame[]; points: KeypointsFrame | null}

export function RecordingPlaybackProvider({recordingId, recordingParentDirectory, getRecordingTime, mediaAvailable, manifest, reloadManifest, onPlaybackRun, children}: {
    recordingId: string | null; recordingParentDirectory: string | null | undefined;
    getRecordingTime: () => number | null; mediaAvailable: boolean; children: ReactNode;
    manifest: PlaybackManifest | null; reloadManifest: () => void; onPlaybackRun: (run: PlaybackRun) => void;
}): React.ReactElement {
    const [runId, setRunId] = useState<number | null>(null);
    const [group, setGroup] = useState('');
    const [error, setError] = useState<string | null>(null);
    const [loaded, setLoaded] = useState<{manifest: PlaybackManifest; runs: Record<string, PlaybackChannelData[]>} | null>(null);
    const [dataTime, setDataTime] = useState(0);
    const [dataPlaying, setDataPlaying] = useState(false);
    const dataTimeRef = useRef(0);
    const state = useRef<PlaybackState>({models: [], frames: [], points: null});
    const modelSubscribers = useRef(new Set<ModelsCallback>());
    const frameSubscribers = useRef(new Set<ModelFramesCallback>());
    const pointSubscribers = useRef(new Set<KeypointsCallback>());
    const fittedDefinitions = useRef<FittedSkeletonDefinition[]>([]);
    const fittedFrames = useRef<FittedSkeletonFrame[]>([]);
    const fittedDefinitionSubscribers = useRef(new Set<(items: FittedSkeletonDefinition[]) => void>());
    const fittedFrameSubscribers = useRef(new Set<(items: FittedSkeletonFrame[]) => void>());
    const run = manifest?.runs.find(item => item.run_id === runId);
    const clock = run?.timelines.find(item => item.sensor_group === group && item.source === `timing:${group}`);
    const groups = [...new Set(run?.channels.map(channel => channel.sensor_group) ?? [])];
    const baseUrl = recordingId ? `${serverUrls.getHttpUrl()}/freemocap/playback/${encodeURIComponent(recordingId)}` : null;
    const parameters = new URLSearchParams();
    if (recordingParentDirectory) parameters.set('recording_parent_directory', recordingParentDirectory);
    const query = parameters.toString();

    useEffect(() => {
        setError(null);
        state.current = {models: [], frames: [], points: null};
        fittedDefinitions.current = []; fittedFrames.current = [];
        fittedDefinitionSubscribers.current.forEach(cb => cb([]));
        fittedFrameSubscribers.current.forEach(cb => cb([]));
        modelSubscribers.current.forEach(callback => callback([]));
        frameSubscribers.current.forEach(callback => callback([]));
        pointSubscribers.current.forEach(callback => callback({pointNames: [], interleaved: new Float32Array()}));
        if (!manifest) return;
        const selected = manifest.runs.find(item => item.run_id === manifest.selected_run_id);
        if (!selected) {setError('Selected recording result is missing'); return;}
        setRunId(selected.run_id); setGroup(selected.channels[0]?.sensor_group ?? '');
        setDataPlaying(false);
    }, [manifest]);

    useEffect(() => {if (run) onPlaybackRun(run);}, [run, onPlaybackRun]);

    // Decode once per manifest; seeking and selecting a run reuse the retained arrays.
    useEffect(() => {
        setLoaded(null);
        if (!manifest || !baseUrl) return;
        const parameters = new URLSearchParams(query);
        parameters.set('revision', manifest.revision);
        const worker = new Worker(new URL('../../services/recording/playback-parquet.worker.ts', import.meta.url), {type: 'module'});
        worker.onmessage = (event: MessageEvent<unknown>) => {
            try {
                const result = PlaybackLoadResultSchema.parse(event.data);
                if (!result.success) throw new Error(result.message);
                setLoaded({manifest, runs: result.runs});
            } catch (failure) {
                setError(failure instanceof Error ? failure.message : String(failure));
            } finally {
                worker.terminate();
            }
        };
        worker.onerror = event => {
            setError(event.message || 'Unable to decode recording data');
            worker.terminate();
        };
        worker.postMessage({url: `${baseUrl}/parquet?${parameters}`, manifest});
        return () => {
            worker.onmessage = null; worker.onerror = null;
            worker.terminate();
        };
    }, [manifest, baseUrl, query]);

    useEffect(() => {
        if (!run || !manifest || !group) return;
        state.current = {models: run.models, frames: [], points: null};
        fittedDefinitions.current = Object.entries(run.fitted_skeletons ?? {})
            .filter(([, definition]) => definition.sensor_group === group).map(([source, definition]) => ({source, definition}));
        fittedFrames.current = [];
        fittedDefinitionSubscribers.current.forEach(cb => cb(fittedDefinitions.current));
        fittedFrameSubscribers.current.forEach(cb => cb([]));
        modelSubscribers.current.forEach(callback => callback(run.models));
        frameSubscribers.current.forEach(callback => callback([]));
        pointSubscribers.current.forEach(callback => callback({pointNames: [], interleaved: new Float32Array()}));
        if (!clock?.timestamps_s.length) {setError('Recording has no synchronized timeline for this group'); return;}
        if (loaded?.manifest !== manifest) return;
        const channels = loaded.runs[run.run_id];
        if (!channels) {setError('Selected recording samples are missing'); return;}
        let raf = 0;
        let emittedTime = NaN;
        const warnedLayers = new Set<string>();
        const sample = <T,>(layer: string, time: number, read: () => T, empty: T): T => {
            try {return read();} catch (failure) {
                if (!warnedLayers.has(layer)) {
                    warnedLayers.add(layer);
                    console.warn('Skipping invalid recording sample; playback will continue', {layer, time, failure});
                }
                return empty;
            }
        };
        const tick = (): void => {
            const time = mediaAvailable ? getRecordingTime() : dataTimeRef.current;
            if (time === null) {
                if (!Number.isNaN(emittedTime)) {
                    state.current.frames = []; state.current.points = null;
                    fittedFrames.current = [];
                    fittedFrameSubscribers.current.forEach(cb => cb([]));
                    emittedTime = NaN;
                    frameSubscribers.current.forEach(callback => callback([]));
                    pointSubscribers.current.forEach(callback => callback({pointNames: [], interleaved: new Float32Array()}));
                }
            } else if (time !== emittedTime) {
                    state.current.frames = run.models.flatMap(model => sample(`model:${model.model_id}`, time,
                        () => [recordedModelFrame(run, {channels}, model, group, time)], []));
                    fittedFrames.current = sample('fitted', time, () => fittedSkeletonFrames(run, channels, group, time), []);
                    fittedFrameSubscribers.current.forEach(cb => cb(fittedFrames.current));
                    const points = sample('original keypoints', time, () => recordedKeypoints(channels, group, time), null);
                    state.current.points = points ? {pointNames: points.names, interleaved: points.data} : null;
                    frameSubscribers.current.forEach(callback => callback(state.current.frames));
                    pointSubscribers.current.forEach(callback => callback(state.current.points ?? {pointNames: [], interleaved: new Float32Array()}));
                    emittedTime = time;
            }
            raf = requestAnimationFrame(tick);
        };
        raf = requestAnimationFrame(tick);
        return () => cancelAnimationFrame(raf);
    }, [run, manifest, loaded, group, getRecordingTime, clock, mediaAvailable]);

    useEffect(() => {
        if (!clock || mediaAvailable) return;
        const start = clock.timestamps_s[0];
        if (start === undefined) return;
        dataTimeRef.current = start; setDataTime(start); setDataPlaying(false);
    }, [clock, mediaAvailable]);

    useEffect(() => {
        if (!dataPlaying || mediaAvailable || !clock) return;
        const end = clock.timestamps_s[clock.timestamps_s.length - 1];
        let previous = performance.now();
        let raf = 0;
        const advance = (now: number): void => {
            dataTimeRef.current = Math.min(end, dataTimeRef.current + (now - previous) / 1000);
            previous = now;
            setDataTime(dataTimeRef.current);
            if (dataTimeRef.current >= end) { setDataPlaying(false); return; }
            raf = requestAnimationFrame(advance);
        };
        raf = requestAnimationFrame(advance);
        return () => cancelAnimationFrame(raf);
    }, [dataPlaying, mediaAvailable, clock]);

    const source = useMemo<KeypointsSource>(() => ({
        subscribeToFittedDefinitions: cb => {fittedDefinitionSubscribers.current.add(cb); cb(fittedDefinitions.current); return () => {fittedDefinitionSubscribers.current.delete(cb);};},
        subscribeToFittedFrames: cb => {fittedFrameSubscribers.current.add(cb); cb(fittedFrames.current); return () => {fittedFrameSubscribers.current.delete(cb);};},
        isLive: false,
        getModels: () => state.current.models,
        getLatestModelFrames: () => state.current.frames,
        getLatestKeypoints: () => state.current.points,
        subscribeToModels: callback => { modelSubscribers.current.add(callback); callback(state.current.models); return () => { modelSubscribers.current.delete(callback); }; },
        subscribeToModelFrames: callback => { frameSubscribers.current.add(callback); callback(state.current.frames); return () => { frameSubscribers.current.delete(callback); }; },
        subscribeToKeypoints: callback => { pointSubscribers.current.add(callback); if (state.current.points) callback(state.current.points); return () => { pointSubscribers.current.delete(callback); }; },
    }), []);

    return <KeypointsSourceProvider source={source}><div className="flex flex-col h-full">
        {!mediaAvailable && clock && <div className="flex items-center gap-2 p-1">
            <button disabled={loaded?.manifest !== manifest || !!error} onClick={() => setDataPlaying(value => !value)}>{dataPlaying ? 'Pause' : 'Play data'}</button>
            <input aria-label="Recording time" type="range" min={clock.timestamps_s[0]} max={clock.timestamps_s[clock.timestamps_s.length - 1]}
                step="any" value={dataTime} onChange={event => {dataTimeRef.current = Number(event.target.value); setDataTime(dataTimeRef.current);}} />
            <span>{dataTime.toFixed(3)} s</span>
        </div>}
        {manifest && loaded?.manifest !== manifest && !error && <p role="status" className="p-2">Loading recording data…</p>}
        {error && <p role="alert" className="text-error p-2">{error}</p>}
        {!manifest && !error && <p className="p-2">No reconstruction loaded.</p>}
        <div className="flex-1 min-h-0" style={{position: 'relative'}}>
        {children}
        <details style={{position: 'absolute', top: 8, left: '50%', transform: 'translateX(-50%)', zIndex: 10, width: 'max-content', maxWidth: 'calc(100% - 16px)', color: '#eee'}}>
            <summary aria-label="Recording results" title="Recording results" className="viewport-options br-1"
                style={{display: 'flex', alignItems: 'center', justifyContent: 'center', width: 28, height: 28, margin: '0 auto', cursor: 'pointer', listStyle: 'none', background: '#20252bee'}}>
                <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                    <path d="M4 6h16M4 12h16M4 18h16" />
                    <path d="M8 4v4M16 10v4M10 16v4" />
                </svg>
            </summary>
        <div className="viewport-options flex items-center gap-2 p-2 br-1" style={{flexWrap: 'wrap', marginTop: 4, background: '#20252bee'}}>
            <label>Result <select value={runId ?? ''} onChange={event => {
                const selected = manifest?.runs.find(item => item.run_id === Number(event.target.value));
                setRunId(Number(event.target.value)); setGroup(selected?.channels[0]?.sensor_group ?? '');
            }}>
                {manifest?.runs.map(item => <option key={item.run_id} value={item.run_id}>{item.run_id}</option>)}
            </select></label>
            <label>Sensor group <select value={group} onChange={event => setGroup(event.target.value)}>
                {groups.map(name => <option key={name} value={name}>{name}</option>)}
            </select></label>
            <button onClick={reloadManifest}>Reload result</button>
            <span>{Object.values(run?.channels.find(item => item.sensor_group === group && item.kind === RecordingChannelKind.Landmarks)?.components ?? {})[0]}</span>
        </div>
        </details>
        </div>
    </div></KeypointsSourceProvider>;
}
