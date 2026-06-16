import {useAppSelector} from "@/store/hooks";
import {
    selectIsPipelineConnected,
    selectIsPipelineLoading,
    selectPipelineError,
    selectPipelineId,
} from "@/store/slices/realtime";

/**
 * Display-only status badge.
 *
 * Connection actions live exclusively in RealtimePipelineConnectionToggle.
 * This component never dispatches — it just reflects Redux state.
 * Previously it had its own click handler that duplicated Toggle's dispatch
 * calls, which created two independent power buttons fighting each other.
 */
export const RealtimePipelineConnectionStatus = () => {
    const isConnected = useAppSelector(selectIsPipelineConnected);
    const pipelineId = useAppSelector(selectPipelineId);
    const isLoading = useAppSelector(selectIsPipelineLoading);
    const error = useAppSelector(selectPipelineError);

    return (
        <div
            className="flex flex-col flex-end br-2"
            style={{
                padding: '10px',
                paddingLeft: 32,
                border: '4px solid rgb(0, 125, 125)',
                backgroundColor: isConnected ? '#005d94' : '#395067',
            }}
        >
            <div className="flex flex-row items-center gap-1">
                <div
                    className="mr-2 br-1 flex items-center justify-center p-1"
                    style={{
                        border: `1px solid ${isConnected ? 'rgba(0,255,255,0.5)' : 'rgba(255,0,0,0.5)'}`,
                        width: '24px',
                        height: '24px',
                        transition: 'background-color 0.3s, border-color 0.3s',
                        backgroundColor: isConnected ? 'rgba(0,255,255,0.1)' : 'rgba(255,0,0,0.1)',
                        boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
                    }}
                >
                    {isLoading ? (
                        <span className="icon loader-icon icon-size-20" />
                    ) : isConnected ? (
                        <span style={{color: 'green', fontSize: 16, fontWeight: 700}}>✓</span>
                    ) : (
                        <span style={{color: 'red', fontSize: 16, fontWeight: 700}}>✕</span>
                    )}
                </div>

                <p className="text md text-white">
                    Pipeline: {isConnected ? `connected (id: ${pipelineId})` : 'disconnected'}
                </p>

                {error && (
                    <p className="text sm text-error ml-2">
                        {error}
                    </p>
                )}
            </div>
        </div>
    );
};

export default RealtimePipelineConnectionStatus;
