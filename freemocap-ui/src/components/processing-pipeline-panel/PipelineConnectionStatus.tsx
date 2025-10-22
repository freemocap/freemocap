import {Box, Typography} from "@mui/material";
import CheckIcon from '@mui/icons-material/Check';
import CloseIcon from '@mui/icons-material/Close';
import {useState} from "react";

export const PipelineConnectionStatus = () => {
    const [isConnected, setIsConnected] = useState(false);
    const [pipelineId, setPipelineId] = useState<string | null>(null);

    const handleToggleConnection = async (e: React.MouseEvent) => {
        e.stopPropagation();
        if (isConnected) {
            console.log('Disconnecting from pipeline');
        } else {
            console.log('Connecting to pipeline');
        }
        setIsConnected(!isConnected);
    };

    return (
        <Box
            sx={{
                display: 'flex',
                justifyContent: 'flex-end',
                padding: '10px',
                flexDirection: 'column',
                pl: 4,
                cursor: 'pointer',
                border: '4px solid rgb(0, 125, 125)',
                backgroundColor: isConnected ? '#005d94' : '#395067',
                borderRadius: '8px',
                ':hover': {
                    backgroundColor: 'rgba(255, 255, 255, 0.05)',
                    borderColor: 'rgb(0,225, 225)',
                },
            }}
            onClick={handleToggleConnection}
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
                    cursor: 'pointer',
                    borderRadius: '4px',
                    transition: 'background-color 0.3s, border-color 0.3s',
                    backgroundColor: isConnected ? 'rgba(0, 255, 255, 0.1)' : 'rgba(255, 0, 0, 0.1)',
                    borderColor: isConnected ? 'rgba(0, 255, 255, 0.5)' : 'rgba(255, 0, 0, 0.5)',
                    boxShadow: '0 2px 4px rgba(0, 0, 0, 0.1)',
                    display: 'flex',
                    alignItems: 'center',
                    padding: '4px',
                    justifyContent: 'center',
                    '&:hover': {
                        backgroundColor: 'rgba(255, 255, 255, 0.05)',
                        borderColor: 'rgba(255, 255, 255, 0.2)',
                    },
                }}>
                    {isConnected ? (
                        <CheckIcon sx={{ color: 'green' }} />
                    ) : (
                        <CloseIcon fontSize="small" sx={{ color: 'red' }} />
                    )}
                </Box>
                Pipeline: {isConnected ? `connected (id:${pipelineId})` : 'disconnected'}
            </Typography>
        </Box>
    );
};
export default PipelineConnectionStatus;
