import React from "react";
import {useAppDispatch, useAppSelector} from "@/store/hooks";
import {
    applyRealtimePipeline,
    closePipeline,
    selectCanConnectPipeline,
    selectCanDisconnectPipeline,
    selectIsPipelineConnected,
    selectIsPipelineLoading,
    selectPipelineConfig,
} from "@/store/slices/realtime";

export const RealtimePipelineConnectionToggle: React.FC = () => {
    const dispatch = useAppDispatch();

    const isConnected = useAppSelector(selectIsPipelineConnected);
    const isLoading = useAppSelector(selectIsPipelineLoading);
    const canConnect = useAppSelector(selectCanConnectPipeline);
    const canDisconnect = useAppSelector(selectCanDisconnectPipeline);
    const pipelineConfig = useAppSelector(selectPipelineConfig);

    const isClickable = canConnect || canDisconnect;

    const handleToggle = async (e: React.MouseEvent): Promise<void> => {
        e.stopPropagation();
        if (isLoading) return;

        if (isConnected) {
            await dispatch(closePipeline());
        } else {
            await dispatch(applyRealtimePipeline(pipelineConfig));
        }
    };

    const tooltipText = isConnected
        ? "Disconnect pipeline"
        : canConnect
            ? "Connect pipeline"
            : "Select cameras first";

    return (
        <button
            className="button icon-button br-1"
            onClick={handleToggle}
            disabled={!isClickable || isLoading}
            title={tooltipText}
            style={{
                border: isConnected ? '1.5px solid var(--color-success)' : '1.5px solid rgba(255,255,255,0.25)',
                backgroundColor: isConnected ? 'rgba(76,175,80,0.2)' : 'transparent',
            }}
        >
            {isLoading ? (
                <span className="icon loader-icon icon-size-20" />
            ) : (
                <span className="icon streaming-icon icon-size-20" />
            )}
        </button>
    );
};
