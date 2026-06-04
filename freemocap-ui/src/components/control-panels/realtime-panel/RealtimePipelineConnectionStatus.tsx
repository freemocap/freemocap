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
            className="flex flex-col"
            style={{
                justifyContent: 'flex-end',
                padding: '10px',
                paddingLeft: 32,
                border: '4px solid rgb(0, 125, 125)',
                backgroundColor: isConnected ? '#005d94' : '#395067',
                borderRadius: '8px',
            }}
        >
            <div className="flex flex-row items-center gap-1">
                <div
                    style={{
                        border: `1px solid ${isConnected ? 'rgba(0,255,255,0.5)' : 'rgba(255,0,0,0.5)'}`,
                        width: '24px',
                        height: '24px',
                        marginRight: '8px',
                        borderRadius: '4px',
                        transition: 'background-color 0.3s, border-color 0.3s',
                        backgroundColor: isConnected ? 'rgba(0,255,255,0.1)' : 'rgba(255,0,0,0.1)',
                        boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
                        display: 'flex',
                        alignItems: 'center',
                        padding: '4px',
                        justifyContent: 'center',
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
                    <p className="text sm text-error" style={{marginLeft: 8}}>
                        {error}
                    </p>
                )}
            </div>
        </div>
    );
};

export default RealtimePipelineConnectionStatus;
