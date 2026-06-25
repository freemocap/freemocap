import {useEffect} from 'react';
import {useAppDispatch, useAppSelector} from '@/store/hooks';
import {
    applyRealtimePipeline,
    selectIsPipelineConnected,
    selectPipelineConfig,
} from '@/store/slices/realtime';
import {
    broadcastRealtimePipelineState,
    subscribeRealtimePipelineBroadcast,
    type RealtimePipelineBroadcastState,
} from '@/services/realtime-pipeline-broadcast';

/**
 * Keeps the main window's realtime pipeline state in sync with auxiliary
 * renderer windows (e.g. pipeline metrics) via BroadcastChannel.
 */
export function useRealtimePipelineBroadcastPublisher(enabled = true): void {
    const dispatch = useAppDispatch();
    const isConnected = useAppSelector(selectIsPipelineConnected);
    const pipelineConfig = useAppSelector(selectPipelineConfig);
    const logPipelineTimes = pipelineConfig.log_pipeline_times !== false;

    useEffect(() => {
        if (!enabled) return;
        const state: RealtimePipelineBroadcastState = {
            isConnected,
            logPipelineTimes,
        };
        broadcastRealtimePipelineState(state);
    }, [enabled, isConnected, logPipelineTimes]);

    useEffect(() => {
        if (!enabled) return;
        return subscribeRealtimePipelineBroadcast((message) => {
            if (message.type === 'request-state') {
                broadcastRealtimePipelineState({
                    isConnected,
                    logPipelineTimes,
                });
                return;
            }
            if (message.type !== 'set-log-pipeline-times' || !isConnected) {
                return;
            }
            dispatch(applyRealtimePipeline({
                ...pipelineConfig,
                log_pipeline_times: message.enabled,
            }));
        });
    }, [dispatch, enabled, isConnected, logPipelineTimes, pipelineConfig]);
}
