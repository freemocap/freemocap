import React from 'react';
import {Box} from '@mui/material';
import {useWebSocketContext} from '@/context/WebSocketContext';

const WebsocketConnection = () => {
    const {isConnected, messages} = useWebSocketContext();

    return (
        <Box sx={{display: 'flex', flexDirection: 'column'}}>
            Websocket status: {isConnected ? 'connected' : 'disconnected'}
        </Box>
    );
};

export default WebsocketConnection
