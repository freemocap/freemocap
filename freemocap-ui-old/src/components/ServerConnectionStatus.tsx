import React from "react";
import {Box, Chip, Tooltip, useTheme} from "@mui/material";
import WifiIcon from "@mui/icons-material/Wifi";
import WifiOffIcon from "@mui/icons-material/WifiOff";
import CheckIcon from "@mui/icons-material/Check";
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

    // Original cyan/red color mapping
    const colors = isConnected
        ? {
            bg: "rgba(0, 255, 255, 0.1)",
            border: "rgba(0, 255, 255, 0.5)",
            text: "#00ffff",
            hoverBg: "rgba(0, 255, 255, 0.2)",
        }
        : {
            bg: "rgba(255, 0, 0, 0.1)",
            border: "rgba(255, 0, 0, 0.5)",
            text: "#f44336",
            hoverBg: "rgba(255, 0, 0, 0.2)",
        };

    return (
        <CollapsibleSidebarSection
            icon={
                isConnected ? (
                    <WifiIcon sx={{color: "inherit"}} />
                ) : (
                    <WifiOffIcon sx={{color: "inherit"}} />
                )
            }
            title="WebSocket"
            summaryContent={
                isConnected && connectedCameraIds.length > 0 ? (
                    <Chip
                        label={`${connectedCameraIds.length} cam${connectedCameraIds.length !== 1 ? "s" : ""}`}
                        size="small"
                        variant="outlined"
                        sx={{
                            height: 18,
                            fontSize: 10,
                            borderColor: "rgba(255,255,255,0.4)",
                            color: "inherit",
                        }}
                    />
                ) : null
            }
            primaryControl={
                <Tooltip title={isConnected ? "Click to disconnect" : "Click to connect"}>
                    <Box
                        onClick={handleToggle}
                        sx={{
                            display: "flex",
                            alignItems: "center",
                            gap: 0.75,
                            cursor: "pointer",
                            borderRadius: 1,
                            border: `2px solid ${colors.border}`,
                            backgroundColor: colors.bg,
                            px: 2,
                            py: 0.5,
                            transition: "all 0.2s ease",
                            "&:hover": {
                                backgroundColor: colors.hoverBg,
                                transform: "translateY(-1px)",
                                boxShadow: `0 2px 8px ${colors.border}`,
                            },
                        }}
                    >
                        {isConnected ? (
                            <CheckIcon sx={{fontSize: 18, color: colors.text}} />
                        ) : null}
                        <Box
                            component="span"
                            sx={{
                                fontSize: 14,
                                fontWeight: 700,
                                lineHeight: 1,
                                color: colors.text,
                                whiteSpace: "nowrap",
                            }}
                        >
                            {isConnected ? "Connected" : "Connect"}
                        </Box>
                    </Box>
                </Tooltip>
            }
            defaultExpanded={false}
        >
            {/* Future: server address, port, reconnect behavior settings */}
            <Box sx={{p: 2, color: theme.palette.text.secondary, fontSize: 14}}>
                {isConnected
                    ? "WebSocket connection active. Click the button to disconnect."
                    : "No active connection. Click the button to connect."}
            </Box>
        </CollapsibleSidebarSection>
    );
};
