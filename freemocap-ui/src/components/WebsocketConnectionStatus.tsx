import React from 'react';
import {Box} from '@mui/material';
import {useWebSocketContext} from '@/context/WebSocketContext';

const WebsocketConnectionStatus = () => {
    const {isConnected} = useWebSocketContext();

    return (
        <Box sx={{display: 'flex', flexDirection: 'column', color: '#dadada'}}>
            Websocket: {isConnected ? 'connected' : 'disconnected'}
        </Box>
    );
};

export default WebsocketConnectionStatus
