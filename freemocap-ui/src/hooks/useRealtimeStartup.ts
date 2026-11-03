import {useCallback, useEffect, useRef, useState} from 'react';
import {useAppDispatch, useAppSelector} from '@/store/hooks';
import {applyRealtimePipeline} from '@/store/slices/realtime/realtime-thunks';
import {requestRealtimeStartup, stopRealtimeStartup, StartupStatusCapability, StartupStatusUnavailableError} from '@/services/server/realtime-startup';
import {serverUrls} from '@/constants/server-urls';
import {readStartupWithDeadline, startupStillPending} from '@/services/server/startup-polling';
import type {RealtimeStartupStatus} from '@/types/realtime-startup';
import {isStartupStopped} from '@/services/server/startup-stopped';

/** Poll during startup independently of the long-running apply HTTP request. */
export function useRealtimeStartup() {
    const dispatch = useAppDispatch();
    const serverConnected = useAppSelector(state => state.connection.isConnected);
    const serverPid = useAppSelector(state => state.connection.serverPid);
    const serverIdentity = `${serverUrls.getHttpUrl()}|${serverPid ?? 'unknown'}`;
    const realtime = useAppSelector(state => state.realtime);
    const [snapshot, setSnapshot] = useState<RealtimeStartupStatus | null>(null);
    const [statusError, setStatusError] = useState<string | null>(null);
    const [commandError, setCommandError] = useState<string | null>(null);
    const [commandPending, setCommandPending] = useState(false);
    const [refresh, setRefresh] = useState(0);
    const [statusUnavailable, setStatusUnavailable] = useState(false);
    const capability = useRef(new StartupStatusCapability());

    useEffect(() => {
        if (!serverConnected) {
            capability.current.reset();
            setStatusUnavailable(false);
            if (realtime.applyPending || (snapshot && startupStillPending(snapshot))) {
                setStatusError('Disconnected from the server');
            }
            return;
        }
        if (!capability.current.allows(serverIdentity)) return;
        setStatusUnavailable(false);
        const controller = new AbortController();
        let timer: ReturnType<typeof setTimeout> | undefined;
        let observedStarting = false;
        if (realtime.applyPending) setSnapshot(null);
        async function poll() {
            if (!capability.current.allows(serverIdentity)) return;
            let keepPolling = true;
            try {
                const next = await readStartupWithDeadline(requestRealtimeStartup, controller.signal);
                if (controller.signal.aborted) return;
                observedStarting ||= startupStillPending(next);
                // A prior operation's ready snapshot can arrive before the new
                // apply request reaches the server. Never show it as new readiness.
                const priorOutcome = realtime.applyPending && !observedStarting
                    && (next.status === 'idle' || next.status === 'ready');
                setSnapshot(priorOutcome ? null : next);
                setStatusError(null);
                keepPolling = realtime.applyPending || startupStillPending(next);
            } catch (error) {
                if (controller.signal.aborted) return;
                if (error instanceof StartupStatusUnavailableError) {
                    capability.current.markUnavailable(serverIdentity);
                    setStatusUnavailable(true);
                    setSnapshot(null);
                    setStatusError(null);
                    keepPolling = false;
                } else setStatusError(error instanceof Error ? error.message : String(error));
            }
            if (!controller.signal.aborted && keepPolling) timer = setTimeout(() => {void poll();}, 500);
        }
        void poll();
        return () => {controller.abort(); if (timer !== undefined) clearTimeout(timer);};
        // Snapshot updates do not restart polling or create concurrent requests.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [serverConnected, serverIdentity, realtime.applyPending, realtime.isConnected, refresh]);

    const stop = useCallback(async () => {
        setCommandPending(true);
        setCommandError(null);
        const controller = new AbortController();
        try {
            const next = await readStartupWithDeadline(stopRealtimeStartup, controller.signal);
            setSnapshot(next);
            setRefresh(value => value + 1);
        } catch (error) {
            if (error instanceof StartupStatusUnavailableError) {
                capability.current.markUnavailable(serverIdentity);
                setStatusUnavailable(true);
                setSnapshot(null);
            } else setCommandError(`Stop request was not confirmed: ${error instanceof Error ? error.message : String(error)}`);
        } finally {setCommandPending(false);}
    }, [serverIdentity]);

    const retry = useCallback(async () => {
        setCommandError(null);
        setSnapshot(null);
        try {
            await dispatch(applyRealtimePipeline(realtime.lastApplyConfig ?? realtime.pipelineConfig)).unwrap();
        } catch (error) {
            if (!isStartupStopped(error)) setCommandError(error instanceof Error ? error.message : String(error));
        }
    }, [dispatch, realtime.lastApplyConfig, realtime.pipelineConfig]);

    const visible = snapshot?.status === 'ready' && !realtime.isConnected && !realtime.applyPending ? null : snapshot;
    return {snapshot: visible, pending: realtime.applyPending, statusError: commandError ?? statusError, statusUnavailable,
        stop: !statusUnavailable && !commandPending && serverConnected ? stop : undefined,
        retry: !statusUnavailable && !commandPending && serverConnected && !realtime.applyPending ? retry : undefined};
}
