import {Box, CircularProgress, Typography} from "@mui/material";
import CheckIcon from '@mui/icons-material/Check';
import CloseIcon from '@mui/icons-material/Close';
import {useAppDispatch, useAppSelector} from "@/store/hooks";
import {
    connectPipeline,
    closePipeline,
    selectCanConnectPipeline,
    selectCanDisconnectPipeline,
    selectIsPipelineConnected,
    selectIsPipelineLoading,
    selectPipelineError,
    selectPipelineId,
} from "@/store/slices/pipeline";

export const PipelineConnectionStatus = () => {
    const dispatch = useAppDispatch();

    const isConnected = useAppSelector(selectIsPipelineConnected);
    const pipelineId = useAppSelector(selectPipelineId);
    const isLoading = useAppSelector(selectIsPipelineLoading);
    const error = useAppSelector(selectPipelineError);
    const canConnect = useAppSelector(selectCanConnectPipeline);
    const canDisconnect = useAppSelector(selectCanDisconnectPipeline);

    const handleToggleConnection = async (e: React.MouseEvent) => {
        e.stopPropagation();

        if (isLoading) return;

        if (isConnected) {
            console.log('Disconnecting from pipeline');
            await dispatch(closePipeline());
        } else {
            console.log('Connecting to pipeline');
            await dispatch(connectPipeline(undefined));
        }
    };

    const isClickable = canConnect || canDisconnect;

    return (
        <Box
            sx={{
                display: 'flex',
                justifyContent: 'flex-end',
                padding: '10px',
                flexDirection: 'column',
                pl: 4,
                cursor: isClickable ? 'pointer' : 'not-allowed',
                border: '4px solid rgb(0, 125, 125)',
                backgroundColor: isConnected ? '#005d94' : '#395067',
                borderRadius: '8px',
                opacity: isClickable ? 1 : 0.6,
                ':hover': isClickable ? {
                    backgroundColor: 'rgba(255, 255, 255, 0.05)',
                    borderColor: 'rgb(0, 225, 225)',
                } : {},
            }}
            onClick={isClickable ? handleToggleConnection : undefined}
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
                    cursor: isClickable ? 'pointer' : 'not-allowed',
                    borderRadius: '4px',
                    transition: 'background-color 0.3s, border-color 0.3s',
                    backgroundColor: isConnected ? 'rgba(0, 255, 255, 0.1)' : 'rgba(255, 0, 0, 0.1)',
                    borderColor: isConnected ? 'rgba(0, 255, 255, 0.5)' : 'rgba(255, 0, 0, 0.5)',
                    boxShadow: '0 2px 4px rgba(0, 0, 0, 0.1)',
                    display: 'flex',
                    alignItems: 'center',
                    padding: '4px',
                    justifyContent: 'center',
                    '&:hover': isClickable ? {
                        backgroundColor: 'rgba(255, 255, 255, 0.05)',
                        borderColor: 'rgba(255, 255, 255, 0.2)',
                    } : {},
                }}>
                    {isLoading ? (
                        <CircularProgress size={16} sx={{ color: 'cyan' }} />
                    ) : isConnected ? (
                        <CheckIcon sx={{ color: 'green' }} />
                    ) : (
                        <CloseIcon fontSize="small" sx={{ color: 'red' }} />
                    )}
                </Box>
                Pipeline: {isConnected ? `connected (id: ${pipelineId})` : 'disconnected'}
                {error && (
                    <Typography variant="caption" color="error" sx={{ ml: 1 }}>
                        {error}
                    </Typography>
                )}
            </Typography>
        </Box>
    );
};

export default PipelineConnectionStatus;
