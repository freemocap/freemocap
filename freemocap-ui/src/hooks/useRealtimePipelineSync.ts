import {useCallback} from "react";
import {useAppDispatch, useAppSelector} from "@/store/hooks";
import {
    applyRealtimePipeline,
    closePipeline,
    pipelineConfigUpdated,
    selectAggregatorConfig,
    selectCameraNodeConfig,
    selectCanConnectPipeline,
    selectCanDisconnectPipeline,
    selectIsPipelineConnected,
    selectIsPipelineLoading,
    selectPipelineConfig,
} from "@/store/slices/realtime";
import {RealtimePipelineConfig} from "@/store/slices/realtime/realtime-types";

/**
 * Shared realtime-pipeline sync logic used by the Realtime Pipeline sidebar panel,
 * the streaming-view settings overlay, and the RTP settings modals — keeping all of
 * them in sync with the same `realtime` slice state and apply/connect behavior.
 */
export function useRealtimePipelineSync() {
    const dispatch = useAppDispatch();

    const isConnected = useAppSelector(selectIsPipelineConnected);
    const isLoading = useAppSelector(selectIsPipelineLoading);
    const canConnect = useAppSelector(selectCanConnectPipeline);
    const canDisconnect = useAppSelector(selectCanDisconnectPipeline);
    const pipelineConfig = useAppSelector(selectPipelineConfig);
    const cameraNodeConfig = useAppSelector(selectCameraNodeConfig);
    const aggregatorConfig = useAppSelector(selectAggregatorConfig);

    /** Applies a new pipeline config live if connected, otherwise updates local config only. */
    const applyOrUpdatePipelineConfig = useCallback(
        (newConfig: RealtimePipelineConfig) => {
            if (isConnected) {
                dispatch(applyRealtimePipeline(newConfig));
            } else {
                dispatch(pipelineConfigUpdated(newConfig));
            }
        },
        [dispatch, isConnected]
    );

    /** Re-applies the current pipeline config if connected — call after a mocap detector/filter config change. */
    const triggerRealtimeApply = useCallback(() => {
        if (isConnected) {
            dispatch(applyRealtimePipeline(pipelineConfig));
        }
    }, [dispatch, isConnected, pipelineConfig]);

    /** Connects or disconnects the realtime pipeline. */
    const toggleConnection = useCallback(async () => {
        if (isLoading) return;
        if (isConnected) {
            await dispatch(closePipeline());
        } else {
            await dispatch(applyRealtimePipeline(pipelineConfig));
        }
    }, [dispatch, isConnected, isLoading, pipelineConfig]);

    return {
        isConnected,
        isLoading,
        canConnect,
        canDisconnect,
        pipelineConfig,
        cameraNodeConfig,
        aggregatorConfig,
        applyOrUpdatePipelineConfig,
        triggerRealtimeApply,
        toggleConnection,
    };
}
