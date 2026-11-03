import {useCallback, useEffect, useRef, useState} from 'react';
import {useAppSelector} from '@/store/hooks';
import {serverUrls} from '@/constants/server-urls';
import {StartupStatusCapability, StartupStatusUnavailableError} from '@/services/server/realtime-startup';
import {boundedPreparationRequest, preparationWorking, PreparationPipelineAvailability, PreparationPipelineUnavailableError, type PreparationAction} from '@/services/server/onnx-preparation';
import type {OnnxPreparation} from '@/types/onnx-preparation';

export function useOnnxPreparation(pipelineId: string | null, open: boolean) {
    const connected = useAppSelector(state => state.connection.isConnected);
    const pid = useAppSelector(state => state.connection.serverPid);
    const identity = `${serverUrls.getHttpUrl()}|${pid ?? 'unknown'}`;
    const capability = useRef(new StartupStatusCapability());
    const pipelineAvailability = useRef(new PreparationPipelineAvailability());
    const [snapshot, setSnapshot] = useState<OnnxPreparation | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [unavailable, setUnavailable] = useState(false);
    const [busy, setBusy] = useState(false);
    const [refresh, setRefresh] = useState(0);
    const generation = useRef(0);

    useEffect(() => {
        const current = ++generation.current;
        setSnapshot(null); setError(null); setBusy(false);
        if (!connected) {capability.current.reset(); pipelineAvailability.current.reset(); setUnavailable(false); return;}
        if (!open) return;
        if (!pipelineId) return;
        if (!capability.current.allows(identity)) {setUnavailable(true); return;}
        setUnavailable(false);
        const unavailableReason = pipelineAvailability.current.reason(identity, pipelineId);
        if (unavailableReason) {setError(unavailableReason); return;}
        const controller = new AbortController();
        let timer: ReturnType<typeof setTimeout> | undefined;
        async function poll() {
            if (!capability.current.allows(identity) || pipelineAvailability.current.reason(identity, pipelineId!)) return;
            let again = false;
            try {
                const next = await boundedPreparationRequest(pipelineId!, 'status', controller.signal);
                if (controller.signal.aborted || generation.current !== current) return;
                setSnapshot(next); setError(null);
                again = preparationWorking(next);
            } catch (failure) {
                if (controller.signal.aborted || generation.current !== current) return;
                if (failure instanceof StartupStatusUnavailableError) {
                    capability.current.markUnavailable(identity); setUnavailable(true); again = false;
                } else if (failure instanceof PreparationPipelineUnavailableError) {
                    pipelineAvailability.current.markUnavailable(identity, pipelineId!, failure.message);
                    setSnapshot(null); setError(failure.message); again = false;
                } else {setError(failure instanceof Error ? failure.message : String(failure));}
            }
            if (again && !controller.signal.aborted) timer = setTimeout(() => {void poll();}, 500);
        }
        void poll();
        return () => {generation.current++; controller.abort(); if (timer !== undefined) clearTimeout(timer);};
    }, [pipelineId, connected, identity, open, refresh]);

    const command = useCallback(async (action: PreparationAction) => {
        if (!open || !pipelineId || !connected || !capability.current.allows(identity) || pipelineAvailability.current.reason(identity, pipelineId)) return;
        const current = generation.current;
        setBusy(true); setError(null);
        try {
            const next = await boundedPreparationRequest(pipelineId, action, new AbortController().signal);
            if (generation.current !== current) return;
            setSnapshot(next); setRefresh(value => value + 1);
        } catch (failure) {
            if (generation.current !== current) return;
            if (failure instanceof StartupStatusUnavailableError) {capability.current.markUnavailable(identity); setUnavailable(true);}
            else setError(`${action === 'stop' ? 'Stop' : 'Preparation'} request was not confirmed: ${failure instanceof Error ? failure.message : String(failure)}`);
        } finally {if (generation.current === current) setBusy(false);}
    }, [pipelineId, connected, identity, open]);

    return {snapshot: pipelineId ? snapshot : null, error: pipelineId ? error : null,
        unavailable: Boolean(pipelineId) && unavailable, busy,
        onPrepare: connected && !unavailable ? () => {void command('prepare');} : undefined,
        onStop: connected && !unavailable ? () => {void command('stop');} : undefined};
}
