import {useEffect, useState} from 'react';
import RecordingPlaybackSession from '@/components/playback/RecordingPlaybackSession';
import PlaybackStatusPanel from '@/components/playback/PlaybackStatusPanel';
import {useAppDispatch, useAppSelector} from '@/store';
import {fetchTaskSnapshot} from '@/store/slices/pipelines/pipelines-thunks';
import {fetchPlaybackBundle, selectPlaybackBundle, selectPlaybackBundleError} from '@/store/slices/playback-data/playback-data-slice';
import {selectActiveRecordingName, selectActiveRecordingBaseDirectory, selectActiveRecordingFullPath} from '@/store/slices/active-recording/active-recording-slice';
import {useServer} from '@/services/server/server-context';

function locationKey(path: string): string {
    const normalized = path.replaceAll('\\', '/').replace(/\/$/, '');
    return /^[a-z]:/i.test(normalized) ? normalized.toLowerCase() : normalized;
}

export default function PlaybackPage(): React.ReactElement {
    const dispatch = useAppDispatch();
    const {isConnected} = useServer();
    const recordingId = useAppSelector(selectActiveRecordingName);
    const parent = useAppSelector(selectActiveRecordingBaseDirectory);
    const path = useAppSelector(selectActiveRecordingFullPath);
    const owners = useAppSelector(state => state.pipelines.recordingOwners);
    const pipelines = useAppSelector(state => state.pipelines.activePipelines);
    const latestTask = Object.values(pipelines).filter(task => task.pipelineId === task.basePipelineId
        && path && locationKey(task.recordingPath) === locationKey(path))
        .sort((a, b) => (b.completedAt ?? 0) - (a.completedAt ?? 0))[0];
    const failure = latestTask?.phase === 'failed' ? latestTask : null;
    const owner = owners.find(item => path && locationKey(item.recording.full_path) === locationKey(path));
    const bundle = useAppSelector(selectPlaybackBundle(recordingId, parent));
    const bundleError = useAppSelector(selectPlaybackBundleError(recordingId, parent));
    const [checked, setChecked] = useState(false);
    const [error, setError] = useState<string | null>(null);
    useEffect(() => {
        setChecked(false); setError(null);
        let active = true;
        const request = dispatch(fetchTaskSnapshot());
        void request.unwrap().then(() => {if (active) setChecked(true);}).catch((failure: unknown) => {
            if (active) setError(String(failure));
        });
        return () => {active = false; request.abort();};
    }, [dispatch, isConnected, path]);
    useEffect(() => {
        if (!checked || !isConnected || owner || !recordingId) return;
        const request = dispatch(fetchPlaybackBundle({recordingId, recordingParentDirectory: parent}));
        return () => {request.abort();};
    }, [dispatch, checked, isConnected, owner, recordingId, parent]);
    if (owner) return <PlaybackStatusPanel title="Processing recording" recording={recordingId ?? ''} failed={false}
        detail="This recording is being processed. Playback is paused while its files are updated and will resume automatically when processing releases it." />;
    if (error || bundleError) return <PlaybackStatusPanel title="Playback could not load" detail={error || bundleError || ''} recording={recordingId ?? ''} failed />;
    if (!checked || !isConnected || (recordingId && !bundle)) return <PlaybackStatusPanel title="Preparing playback" recording={recordingId ?? ''}
        detail="Loading the recording’s videos and reconstruction data." failed={false} />;
    return <div className="flex flex-col h-full min-h-0">
        {failure && <div role="alert" style={{padding: '12px 16px', marginBottom: 8, borderRadius: 8,
            background: 'var(--color-danger-surface)', border: '1px solid var(--color-danger)', color: 'var(--color-text-primary)'}}>
            <strong>Processing failed</strong><p style={{margin: '4px 0 0', fontSize: 13}}>{failure.detail}</p>
        </div>}
        <RecordingPlaybackSession />
    </div>;
}
