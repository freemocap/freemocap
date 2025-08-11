import React from 'react';
import { Box, Typography, IconButton, Tooltip } from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import { useWebSocketContext } from "@/context/websocket-context/WebSocketContext";
import { urlService } from '@/services/urlService';

const WebsocketConnectionStatus = () => {
    const { isConnected, disconnect, connect } = useWebSocketContext();

    const wsUrl = urlService.getWebSocketUrl();
    const handleResetConnection = () => {
        disconnect();
        setTimeout(() => {
            connect();
        }, 500);
    };

    return (
        <Box sx={{
            display: 'flex',
            justifyContent: 'flex-end',
            padding: '10px',
            flexDirection: 'column',
            pl: 4,
            color: '#dadada',
            cursor: 'pointer',
        }}
        onClick={handleResetConnection}
        >
            <Tooltip
                title={`WebSocket URL: ${wsUrl}`}
                placement="bottom-start"
                arrow
            >
                <Typography
                    variant="body1"
                    sx={{ 
                        display: 'flex',
                        alignItems: 'center',
                    }}
                >
                    Websocket: {isConnected ? 'connected ✔️' : 'disconnected❌'}
                    <Tooltip
                        title="Reset WebSocket connection"
                        placement="top"
                        arrow
                    >
                        <IconButton
                            size="small"
                            sx={{
                                ml: 1,
                                color: 'inherit',
                                padding: '4px',
                                '&:hover': {
                                    backgroundColor: 'rgba(255, 255, 255, 0.1)'
                                }
                            }}
                            onClick={(e) => {
                                e.stopPropagation();
                                handleResetConnection();
                            }}
                            aria-label="Reset connection"
                        >
                            <RefreshIcon fontSize="small" />
                        </IconButton>
                    </Tooltip>
                </Typography>
            </Tooltip>
        </Box>
    );
};

export default WebsocketConnectionStatus;