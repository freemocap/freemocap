import {Box, Tooltip, Typography} from "@mui/material";
import {useWebSocketContext} from "@/context/websocket-context/WebSocketContext";
import CheckIcon from '@mui/icons-material/Check';
import CloseIcon from '@mui/icons-material/Close';

const WebsocketConnectionStatus = () => {
    const {isConnected, disconnect, connect} = useWebSocketContext();

    const handleToggleConnection = () => {
        if (isConnected) {
            console.log('Toggling WebSocket: disconnecting');
            disconnect(false);
        } else {
            console.log('Toggling WebSocket: connecting');
            connect();
        }
    };

    return (
        // <Tooltip title={`WebSocket URL: ${wsUrl}`} placement="bottom-start" arrow>
            <Box
                sx={{
                    display: 'flex',
                    justifyContent: 'flex-end',
                    padding: '10px',
                    flexDirection: 'column',
                    pl: 4,
                    color: '#dadada',
                    cursor: 'pointer',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    borderRadius: '8px',
                    ':hover': {
                        backgroundColor: 'rgba(255, 255, 255, 0.05)',
                        borderColor: 'rgba(255, 255, 255, 0.2)',
                    },
                }}
                onClick={handleToggleConnection}
            >
                <Typography
                    variant="body1"
                    component="div" // Override the default <p> to <div>
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
                    Websocket: {isConnected ? 'connected' : 'disconnected'}
                </Typography>
            </Box>
        // </Tooltip>
    )
        ;
};
export default WebsocketConnectionStatus;
