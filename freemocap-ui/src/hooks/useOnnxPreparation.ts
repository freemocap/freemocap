import {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {useAppSelector} from '@/store/hooks';
import {selectRealtimeTasks} from '@/store/slices/pipelines/pipelines-slice';
import {latestRealtimeTask} from '@/services/server/realtime-progress';
import {serverUrls} from '@/constants/server-urls';
import {StartupStatusCapability, StartupStatusUnavailableError} from '@/services/server/realtime-startup';
import {boundedPreparationRequest, PreparationPipelineAvailability, PreparationPipelineUnavailableError, type PreparationAction} from '@/services/server/onnx-preparation';
import {OnnxPreparationSchema, type OnnxPreparation} from '@/types/onnx-preparation';

/** Initial capability read and explicit commands; progress uses the existing websocket. */
export function useOnnxPreparation(pipelineId: string | null, open: boolean) {
    const connected = useAppSelector(state => state.connection.isConnected);
    const pid = useAppSelector(state => state.connection.serverPid);
    const tasks = useAppSelector(selectRealtimeTasks);
    const task = useMemo(() => latestRealtimeTask(tasks, 'onnx_preparation', pipelineId), [tasks, pipelineId]);
    const startup = useMemo(() => latestRealtimeTask(tasks, 'realtime_startup'), [tasks]);
    // Read capabilities once when model loading completes, even if details were
    // opened earlier. This semantic progress event is not a polling clock.
    const readyOperation = startup?.result?.pipeline_id === pipelineId && startup.result.status === 'ready' ? startup.task_id : null;
    const pushed = useMemo(() => task ? OnnxPreparationSchema.safeParse(task.result) : null, [task]);
    const taskVersion = task ? `${task.task_id}:${task.revision}` : null;
    const taskRef = useRef(taskVersion); taskRef.current = taskVersion;
    const identity = `${serverUrls.getHttpUrl()}|${pid ?? 'unknown'}`;
    const capability = useRef(new StartupStatusCapability());
    const pipelineAvailability = useRef(new PreparationPipelineAvailability());
    const [local, setLocal] = useState<{identity: string; basis: typeof taskVersion; snapshot: OnnxPreparation} | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [unavailable, setUnavailable] = useState(false);
    const [busy, setBusy] = useState(false);
    const generation = useRef(0);
    useEffect(() => {
        const current = ++generation.current;
        setLocal(null); setError(null); setBusy(false);
        if (!connected) {capability.current.reset(); pipelineAvailability.current.reset(); setUnavailable(false); return;}
        if (!open || !pipelineId || taskRef.current) return;
        if (!capability.current.allows(identity)) {setUnavailable(true); return;}
        setUnavailable(false);
        const reason = pipelineAvailability.current.reason(identity, pipelineId);
        if (reason) {setError(reason); return;}
        const controller = new AbortController(), basis = taskRef.current;
        void boundedPreparationRequest(pipelineId, 'status', controller.signal).then(snapshot => {
            if (!controller.signal.aborted && generation.current === current && taskRef.current === basis) setLocal({identity, basis, snapshot});
        }).catch(failure => {
            if (controller.signal.aborted || generation.current !== current || taskRef.current !== basis) return;
            if (failure instanceof StartupStatusUnavailableError) {capability.current.markUnavailable(identity); setUnavailable(true);}
            else {
                if (failure instanceof PreparationPipelineUnavailableError) pipelineAvailability.current.markUnavailable(identity, pipelineId, failure.message);
                setError(failure instanceof Error ? failure.message : String(failure));
            }
        });
        return () => {generation.current++; controller.abort();};
    }, [pipelineId, connected, identity, open, readyOperation]);
    const command = useCallback(async (action: PreparationAction) => {
        if (!open || !pipelineId || !connected || (!taskRef.current && !capability.current.allows(identity))) return;
        const current = generation.current, basis = taskRef.current;
        setBusy(true); setError(null);
        try {
            const snapshot = await boundedPreparationRequest(pipelineId, action, new AbortController().signal);
            if (generation.current === current && taskRef.current === basis) setLocal({identity, basis, snapshot});
        } catch (failure) {
            if (generation.current !== current) return;
            if (failure instanceof StartupStatusUnavailableError) {capability.current.markUnavailable(identity); setUnavailable(true);}
            else setError(`${action === 'stop' ? 'Stop' : 'Preparation'} request was not confirmed: ${failure instanceof Error ? failure.message : String(failure)}`);
        } finally {if (generation.current === current) setBusy(false);}
    }, [pipelineId, connected, identity, open]);
    const snapshot = local?.identity === identity && local.basis === taskVersion && local.snapshot.pipeline_id === pipelineId
        ? local.snapshot : pushed?.success ? pushed.data : null;
    return {snapshot: connected && pipelineId ? snapshot : null, error: pipelineId ? error : null,
        unavailable: Boolean(pipelineId) && !pushed?.success && unavailable, busy,
        onPrepare: connected && (!unavailable || pushed?.success) ? () => {void command('prepare');} : undefined,
        onStop: connected && (!unavailable || pushed?.success) ? () => {void command('stop');} : undefined};
}
