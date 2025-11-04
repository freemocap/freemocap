// components/ServerConnectionStatus.tsx
import React from 'react';
import { Box, Typography, IconButton } from "@mui/material";
import CheckIcon from '@mui/icons-material/Check';
import CloseIcon from '@mui/icons-material/Close';
import WifiIcon from '@mui/icons-material/Wifi';
import WifiOffIcon from '@mui/icons-material/WifiOff';

import {useServer} from "@/hooks/useServer";

export const ServerConnectionStatus: React.FC = () => {
    const { isConnected, connect, disconnect, connectedCameraIds } = useServer();

    const handleClick = (): void => {
        if (isConnected) {
            disconnect();
        } else {
            connect();
        }
    };

    const getStatusColor = (): { bg: string; border: string; text: string } => {
        if (isConnected) {
            return {
                bg: 'rgba(0, 255, 255, 0.05)',
                border: 'rgba(0, 255, 255, 0.3)',
                text: '#00ffff'
            };
        }
        return {
            bg: 'rgba(255, 0, 0, 0.1)',
            border: 'rgba(255, 0, 0, 0.3)',
            text: '#f44336'
        };
    };

    const colors = getStatusColor();

    return (
        <Box
            onClick={handleClick}
            sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1,
                padding: '8px 12px',
                cursor: 'pointer',
                border: `1px solid ${colors.border}`,
                borderRadius: '8px',
                backgroundColor: colors.bg,
                transition: 'all 0.2s ease',
                ':hover': {
                    opacity: 0.8,
                    transform: 'translateY(-1px)',
                    boxShadow: '0 2px 8px rgba(0, 0, 0, 0.1)',
                },
            }}
        >
            <IconButton
                size="small"
                sx={{
                    p: 0.5,
                    color: colors.text,
                    backgroundColor: 'rgba(255, 255, 255, 0.1)',
                    ':hover': { backgroundColor: 'rgba(255, 255, 255, 0.2)' }
                }}
            >
                {isConnected ? <WifiIcon /> : <WifiOffIcon />}
            </IconButton>

            <Box>
                <Typography
                    variant="body2"
                    sx={{
                        fontWeight: 500,
                        color: colors.text,
                        display: 'flex',
                        alignItems: 'center',
                        gap: 0.5
                    }}
                >
                    WebSocket: {isConnected ? 'Connected' : 'Disconnected'}
                    {isConnected ? (
                        <CheckIcon sx={{ fontSize: 16 }} />
                    ) : (
                        <CloseIcon sx={{ fontSize: 16 }} />
                    )}
                </Typography>

                {isConnected && connectedCameraIds.length > 0 && (
                    <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                        {connectedCameraIds.length} camera{connectedCameraIds.length !== 1 ? 's' : ''} active
                    </Typography>
                )}

                {!isConnected && (
                    <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                        Click to connect
                    </Typography>
                )}
            </Box>
        </Box>
    );
};
