import React from "react";
import {useRealtimePipelineSync} from "@/hooks/useRealtimePipelineSync";

export const RealtimePipelineConnectionToggle: React.FC = () => {
    const {isConnected, isLoading, canConnect, canDisconnect, toggleConnection} = useRealtimePipelineSync();

    const isClickable = canConnect || canDisconnect;

    const handleToggle = async (e: React.MouseEvent): Promise<void> => {
        e.stopPropagation();
        await toggleConnection();
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
