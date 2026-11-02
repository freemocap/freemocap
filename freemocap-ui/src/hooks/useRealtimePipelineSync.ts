import {useCallback} from "react";
import {store} from '@/store';
import {useAppDispatch, useAppSelector} from "@/store/hooks";
import {
    applyRealtimePipeline,
    closePipeline,
    pipelineConfigUpdated,
    selectAggregatorConfig,
    selectCameraNodeConfig,
    selectIsPipelineConnected,
    selectIsPipelineLoading,
    selectPipelineConfig,
    selectPipelineError,
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
    const error = useAppSelector(selectPipelineError);
    const pipelineConfig = useAppSelector(selectPipelineConfig);
    const cameraNodeConfig = useAppSelector(selectCameraNodeConfig);
    const aggregatorConfig = useAppSelector(selectAggregatorConfig);

    /** Applies a new pipeline config live if connected, otherwise updates local config only. */
    const applyOrUpdatePipelineConfig = useCallback(
        (newConfig: RealtimePipelineConfig) => {
            if (isConnected && (newConfig.camera_node_config.detector_type !== 'dlc' || newConfig.camera_node_config.dlc_model_path)) {
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
            const config = store.getState().realtime.pipelineConfig;
            if (config.camera_node_config.detector_type !== 'dlc' || config.camera_node_config.dlc_model_path) dispatch(applyRealtimePipeline(config));
        }
    }, [dispatch, isConnected]);

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
        error,
        pipelineConfig,
        cameraNodeConfig,
        aggregatorConfig,
        applyOrUpdatePipelineConfig,
        triggerRealtimeApply,
        toggleConnection,
    };
}
