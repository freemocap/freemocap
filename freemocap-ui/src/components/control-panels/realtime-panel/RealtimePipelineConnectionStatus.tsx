import {Box, CircularProgress, Typography} from "@mui/material";
import CheckIcon from '@mui/icons-material/Check';
import CloseIcon from '@mui/icons-material/Close';
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
        <Box
            sx={{
                display: 'flex',
                justifyContent: 'flex-end',
                padding: '10px',
                flexDirection: 'column',
                pl: 4,
                border: '4px solid rgb(0, 125, 125)',
                backgroundColor: isConnected ? '#005d94' : '#395067',
                borderRadius: '8px',
            }}
        >
            <Typography
                variant="body1"
                component="div"
                sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1,
                }}
            >
                <Box sx={{
                    border: '1px solid rgba(255, 255, 255, 0.3)',
                    width: '24px',
                    height: '24px',
                    marginRight: '8px',
                    borderRadius: '4px',
                    transition: 'background-color 0.3s, border-color 0.3s',
                    backgroundColor: isConnected ? 'rgba(0, 255, 255, 0.1)' : 'rgba(255, 0, 0, 0.1)',
                    borderColor: isConnected ? 'rgba(0, 255, 255, 0.5)' : 'rgba(255, 0, 0, 0.5)',
                    boxShadow: '0 2px 4px rgba(0, 0, 0, 0.1)',
                    display: 'flex',
                    alignItems: 'center',
                    padding: '4px',
                    justifyContent: 'center',
                }}>
                    {isLoading ? (
                        <CircularProgress size={16} sx={{color: 'cyan'}} />
                    ) : isConnected ? (
                        <CheckIcon sx={{color: 'green'}} />
                    ) : (
                        <CloseIcon fontSize="small" sx={{color: 'red'}} />
                    )}
                </Box>

                Pipeline: {isConnected ? `connected (id: ${pipelineId})` : 'disconnected'}

                {error && (
                    <Typography variant="caption" color="error" sx={{ml: 1}}>
                        {error}
                    </Typography>
                )}
            </Typography>
        </Box>
    );
};

export default RealtimePipelineConnectionStatus;
