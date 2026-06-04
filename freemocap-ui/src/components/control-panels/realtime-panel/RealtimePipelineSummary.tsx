import React from "react";
import {useAppSelector} from "@/store/hooks";
import {selectIsPipelineConnected, selectPipelineError, selectPipelineId,} from "@/store/slices/realtime";

export const RealtimePipelineSummary: React.FC = () => {
    const isConnected = useAppSelector(selectIsPipelineConnected);
    const pipelineId = useAppSelector(selectPipelineId);
    const error = useAppSelector(selectPipelineError);

    if (error) {
        return (
            <p
                className="text sm text-error text-nowrap"
                style={{fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis'}}
            >
                Error
            </p>
        );
    }

    return (
        <span
            className="tag text sm"
            style={{
                maxWidth: 160,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                fontWeight: 600,
            }}
        >
            {isConnected ? `Active (${pipelineId})` : "Inactive"}
        </span>
    );
};
