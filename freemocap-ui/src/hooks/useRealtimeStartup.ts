import {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {useAppDispatch, useAppSelector} from '@/store/hooks';
import {applyRealtimePipeline} from '@/store/slices/realtime/realtime-thunks';
import {selectRealtimeTasks} from '@/store/slices/pipelines/pipelines-slice';
import {latestRealtimeTask} from '@/services/server/realtime-progress';
import {requestRealtimeStartup, stopRealtimeStartup, StartupStatusCapability, StartupStatusUnavailableError} from '@/services/server/realtime-startup';
import {serverUrls} from '@/constants/server-urls';
import {readStartupWithDeadline} from '@/services/server/startup-polling';
import {RealtimeStartupStatusSchema, type RealtimeStartupStatus} from '@/types/realtime-startup';
import {isStartupStopped} from '@/services/server/startup-stopped';

/** Bootstrap once per connection; transitions use the existing task progress stream. */
export function useRealtimeStartup() {
    const dispatch = useAppDispatch();
    const connected = useAppSelector(state => state.connection.isConnected);
    const pid = useAppSelector(state => state.connection.serverPid);
    const tasks = useAppSelector(selectRealtimeTasks);
    const task = useMemo(() => latestRealtimeTask(tasks), [tasks]);
    const pushed = useMemo(() => task ? RealtimeStartupStatusSchema.safeParse(task.result) : null, [task]);
    const taskVersion = task ? `${task.task_id}:${task.revision}` : null;
    const taskRef = useRef(taskVersion); taskRef.current = taskVersion;
    const identity = `${serverUrls.getHttpUrl()}|${pid ?? 'unknown'}`;
    const realtime = useAppSelector(state => state.realtime);
    const [local, setLocal] = useState<{identity: string; basis: typeof taskVersion; snapshot: RealtimeStartupStatus} | null>(null);
    const [statusError, setStatusError] = useState<string | null>(null);
    const [commandError, setCommandError] = useState<string | null>(null);
    const [commandPending, setCommandPending] = useState(false);
    const [statusUnavailable, setStatusUnavailable] = useState(false);
    const capability = useRef(new StartupStatusCapability());
    const generation = useRef(0), pendingBaseline = useRef(task?.task_id), wasPending = useRef(false);
    if (realtime.applyPending && !wasPending.current) pendingBaseline.current = task?.task_id;
    wasPending.current = realtime.applyPending;
    useEffect(() => {
        const current = ++generation.current;
        setLocal(null); setStatusError(null); setCommandError(null); setCommandPending(false);
        if (!connected) {capability.current.reset(); setStatusUnavailable(false); return;}
        if (taskRef.current || !capability.current.allows(identity)) return;
        setStatusUnavailable(false);
        const controller = new AbortController(), basis = taskRef.current;
        void readStartupWithDeadline(requestRealtimeStartup, controller.signal).then(snapshot => {
            if (!controller.signal.aborted && generation.current === current && taskRef.current === basis) setLocal({identity, basis, snapshot});
        }).catch(error => {
            if (controller.signal.aborted || generation.current !== current || taskRef.current !== basis) return;
            if (error instanceof StartupStatusUnavailableError) {capability.current.markUnavailable(identity); setStatusUnavailable(true);}
            else setStatusError(error instanceof Error ? error.message : String(error));
        });
        return () => {generation.current++; controller.abort();};
    }, [connected, identity]);
    const stop = useCallback(async () => {
        setCommandPending(true); setCommandError(null);
        const current = generation.current, basis = taskRef.current;
        try {
            const snapshot = await readStartupWithDeadline(stopRealtimeStartup, new AbortController().signal);
            if (generation.current === current && taskRef.current === basis) setLocal({identity, basis, snapshot});
        } catch (error) {
            if (generation.current !== current) return;
            if (error instanceof StartupStatusUnavailableError) {capability.current.markUnavailable(identity); setStatusUnavailable(true);}
            else setCommandError(`Stop request was not confirmed: ${error instanceof Error ? error.message : String(error)}`);
        } finally {if (generation.current === current) setCommandPending(false);}
    }, [identity]);
    const retry = useCallback(async () => {
        setCommandError(null); setLocal(null);
        try {await dispatch(applyRealtimePipeline(realtime.lastApplyConfig ?? realtime.pipelineConfig)).unwrap();}
        catch (error) {if (!isStartupStopped(error)) setCommandError(error instanceof Error ? error.message : String(error));}
    }, [dispatch, realtime.lastApplyConfig, realtime.pipelineConfig]);
    const snapshot = local?.identity === identity && local.basis === taskVersion ? local.snapshot : pushed?.success ? pushed.data : null;
    const staleReady = snapshot?.status === 'ready' && ((!realtime.isConnected && !realtime.applyPending)
        || (realtime.applyPending && task?.task_id === pendingBaseline.current));
    return {snapshot: connected && !staleReady ? snapshot : null, pending: realtime.applyPending,
        statusError: commandError ?? (pushed?.success ? null : statusError), statusUnavailable: !pushed?.success && statusUnavailable,
        stop: (!statusUnavailable || pushed?.success) && !commandPending && connected ? stop : undefined,
        retry: (!statusUnavailable || pushed?.success) && !commandPending && connected && !realtime.applyPending ? retry : undefined};
}
