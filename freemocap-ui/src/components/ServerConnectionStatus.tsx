import React from "react";
import {Box, Chip, IconButton, Tooltip, Typography, useTheme} from "@mui/material";
import WifiIcon from "@mui/icons-material/Wifi";
import WifiOffIcon from "@mui/icons-material/WifiOff";
import {CollapsibleSidebarSection} from "@/components/common/CollapsibleSidebarSection";
import {useServer} from "@/hooks/useServer";

export const ServerConnectionStatus: React.FC = () => {
    const theme = useTheme();
    const {isConnected, connect, disconnect, connectedCameraIds} = useServer();

    const handleToggle = (e: React.MouseEvent): void => {
        e.stopPropagation();
        if (isConnected) {
            disconnect();
        } else {
            connect();
        }
    };

    const statusColor = isConnected
        ? theme.palette.success.main
        : theme.palette.error.main;

    return (
        <CollapsibleSidebarSection
            icon={
                isConnected ? (
                    <WifiIcon sx={{color: "inherit"}} />
                ) : (
                    <WifiOffIcon sx={{color: "inherit"}} />
                )
            }
            title="Connection"
            summaryContent={
                <Box sx={{display: "flex", alignItems: "center", gap: 0.75}}>
                    <Chip
                        label={isConnected ? "Connected" : "Disconnected"}
                        size="small"
                        sx={{
                            height: 20,
                            fontSize: 11,
                            fontWeight: 600,
                            backgroundColor: statusColor,
                            color: theme.palette.getContrastText(statusColor),
                        }}
                    />
                    {isConnected && connectedCameraIds.length > 0 && (
                        <Typography
                            variant="caption"
                            sx={{
                                color: "inherit",
                                opacity: 0.8,
                                whiteSpace: "nowrap",
                            }}
                        >
                            {connectedCameraIds.length} cam{connectedCameraIds.length !== 1 ? "s" : ""}
                        </Typography>
                    )}
                </Box>
            }
            primaryControl={
                <Tooltip title={isConnected ? "Disconnect" : "Connect"}>
                    <IconButton
                        size="small"
                        onClick={handleToggle}
                        sx={{
                            color: "inherit",
                            border: `1.5px solid`,
                            borderColor: isConnected
                                ? "rgba(255,255,255,0.4)"
                                : "rgba(255,255,255,0.25)",
                            borderRadius: 1,
                            px: 1,
                            py: 0.25,
                            fontSize: 12,
                            "&:hover": {
                                backgroundColor: "rgba(255,255,255,0.1)",
                            },
                        }}
                    >
                        <Typography variant="caption" sx={{fontWeight: 600, color: "inherit"}}>
                            {isConnected ? "OFF" : "ON"}
                        </Typography>
                    </IconButton>
                </Tooltip>
            }
            defaultExpanded={false}
        >
            {/* Future: server address, port, reconnect behavior settings */}
            <Box sx={{p: 2}}>
                <Typography variant="body2" color="text.secondary">
                    {isConnected
                        ? "WebSocket connection active."
                        : "Click the connect button to establish a WebSocket connection."}
                </Typography>
            </Box>
        </CollapsibleSidebarSection>
    );
};
