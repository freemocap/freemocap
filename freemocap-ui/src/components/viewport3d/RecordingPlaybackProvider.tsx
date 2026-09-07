import {useEffect, useMemo, useRef, useState, type ReactNode} from 'react';
import {serverUrls} from '@/constants/server-urls';
import {KeypointsSourceProvider, type KeypointsSource, type KeypointsFrame, type KeypointsCallback, type ModelsCallback, type ModelFramesCallback} from './KeypointsSourceContext';
import type {ModelDefinition} from '@/services/server/transport/message-contract';
import type {ResolvedModelFrame} from '@/services/server/transport/frame-types';
import {channelFrame, recordedModelFrame, RecordingChannelKind, type PlaybackManifest, type PlaybackWindow, type PlaybackRun} from '@/services/recording/playback-data';

interface PlaybackState {models: ModelDefinition[]; frames: ResolvedModelFrame[]; points: KeypointsFrame | null}

export function RecordingPlaybackProvider({recordingId, recordingParentDirectory, getRecordingTime, mediaAvailable, manifest, reloadManifest, onPlaybackRun, children}: {
    recordingId: string | null; recordingParentDirectory: string | null | undefined;
    getRecordingTime: () => number | null; mediaAvailable: boolean; children: ReactNode;
    manifest: PlaybackManifest | null; reloadManifest: () => void; onPlaybackRun: (run: PlaybackRun) => void;
}): React.ReactElement {
    const [runId, setRunId] = useState<number | null>(null);
    const [group, setGroup] = useState('');
    const [error, setError] = useState<string | null>(null);
    const [dataTime, setDataTime] = useState(0);
    const [dataPlaying, setDataPlaying] = useState(false);
    const dataTimeRef = useRef(0);
    const state = useRef<PlaybackState>({models: [], frames: [], points: null});
    const modelSubscribers = useRef(new Set<ModelsCallback>());
    const frameSubscribers = useRef(new Set<ModelFramesCallback>());
    const pointSubscribers = useRef(new Set<KeypointsCallback>());
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

    useEffect(() => {
        if (!run || !manifest || !baseUrl || !group) return;
        setError(null);
        state.current = {models: run.models, frames: [], points: null};
        modelSubscribers.current.forEach(callback => callback(run.models));
        frameSubscribers.current.forEach(callback => callback([]));
        const timeline = clock;
        if (!timeline?.timestamps_s.length) { setError('Recording has no synchronized timeline for this group'); return; }
        let cached: PlaybackWindow | null = null;
        let prefetched: PlaybackWindow | null = null;
        let pending: AbortController | null = null;
        let pendingStart: number | null = null;
        let raf = 0;
        let disposed = false;
        let failed = false;
        let emittedTime = NaN;
        const emit = (time: number): void => {
            if (!cached || time === emittedTime) return;
            emittedTime = time;
            state.current.frames = run.models.map(model => recordedModelFrame(run, cached!, model, group, time));
            const raw = cached.channels.find(item => item.channel.sensor_group === group && item.channel.kind === RecordingChannelKind.RawPoints);
            const data = raw ? channelFrame(raw, time) : null;
            state.current.points = raw && data ? {pointNames: raw.channel.names, interleaved: data} : null;
            frameSubscribers.current.forEach(callback => callback(state.current.frames));
            if (state.current.points) pointSubscribers.current.forEach(callback => callback(state.current.points!));
        };
        const tick = (): void => {
            if (disposed || failed) return;
            let time: number | null = dataTimeRef.current;
            if (mediaAvailable) {
                time = getRecordingTime();
            }
            if (time === null) {
                state.current.frames = []; state.current.points = null;
                emittedTime = NaN;
                frameSubscribers.current.forEach(callback => callback([]));
                pointSubscribers.current.forEach(callback => callback({pointNames: [], interleaved: new Float32Array()}));
                raf = requestAnimationFrame(tick);
                return;
            }
            if (prefetched && time >= prefetched.start_s && time < prefetched.end_s) {
                cached = prefetched;
                prefetched = null;
                emittedTime = NaN;
            }
            const covered = cached !== null && time >= cached.start_s && time < cached.end_s;
            if (covered) emit(time);
            const needsLookahead = covered && cached !== null && cached.end_s - time < 1.5
                && cached.end_s <= timeline.timestamps_s[timeline.timestamps_s.length - 1];
            if (!covered || (needsLookahead && !prefetched)) {
                const start = covered && cached ? cached.end_s : Math.floor(time) - 0.25;
                // Keep an in-flight window when it already contains the requested time.
                const pendingCoversTime = pendingStart !== null && time >= pendingStart && time < pendingStart + 2.5;
                if (pendingStart === null || (!covered && !pendingCoversTime)) {
                    pending?.abort();
                    const controller = new AbortController();
                    pending = controller; pendingStart = start;
                    void (async () => {
                        try {
                            const response = await fetch(`${baseUrl}/window?${query}`, {method: 'POST',
                                headers: {'Content-Type': 'application/json'}, signal: controller.signal,
                                body: JSON.stringify({revision: manifest.revision, run_id: run.run_id,
                                    sensor_groups: [group], start_s: start, end_s: start + 2.5})});
                            if (!response.ok) throw new Error(`Unable to load recording samples: ${await response.text()}`);
                            const data: PlaybackWindow = await response.json();
                            if (disposed || controller.signal.aborted) return;
                            if (covered) prefetched = data;
                            else { cached = data; prefetched = null; emittedTime = NaN; }
                            pendingStart = null;
                        } catch (failure) {
                            if (!disposed && !controller.signal.aborted) {
                                failed = true; setError(failure instanceof Error ? failure.message : String(failure));
                            }
                        }
                    })();
                }
            }
            raf = requestAnimationFrame(tick);
        };
        raf = requestAnimationFrame(tick);
        return () => { disposed = true; pending?.abort(); cancelAnimationFrame(raf); };
    }, [run, manifest, baseUrl, query, group, getRecordingTime, clock, mediaAvailable]);

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
        getModels: () => state.current.models,
        getLatestModelFrames: () => state.current.frames,
        getLatestKeypoints: () => state.current.points,
        subscribeToModels: callback => { modelSubscribers.current.add(callback); callback(state.current.models); return () => { modelSubscribers.current.delete(callback); }; },
        subscribeToModelFrames: callback => { frameSubscribers.current.add(callback); callback(state.current.frames); return () => { frameSubscribers.current.delete(callback); }; },
        subscribeToKeypoints: callback => { pointSubscribers.current.add(callback); if (state.current.points) callback(state.current.points); return () => { pointSubscribers.current.delete(callback); }; },
    }), []);

    return <KeypointsSourceProvider source={source}><div className="flex flex-col h-full">
        <div className="flex items-center gap-2 p-1">
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
        {!mediaAvailable && clock && <div className="flex items-center gap-2 p-1">
            <button onClick={() => setDataPlaying(value => !value)}>{dataPlaying ? 'Pause' : 'Play data'}</button>
            <input aria-label="Recording time" type="range" min={clock.timestamps_s[0]} max={clock.timestamps_s[clock.timestamps_s.length - 1]}
                step="any" value={dataTime} onChange={event => {dataTimeRef.current = Number(event.target.value); setDataTime(dataTimeRef.current);}} />
            <span>{dataTime.toFixed(3)} s</span>
        </div>}
        {error && <p role="alert" className="text-error p-2">{error}</p>}
        {!manifest && !error && <p className="p-2">No reconstruction loaded.</p>}
        <div className="flex-1 min-h-0">{children}</div>
    </div></KeypointsSourceProvider>;
}
