import {Box, Button} from "@mui/material";
import React from "react";
import {ConnectToCamerasButton} from "@/components/ConnectToCamerasButton";
import {useWebSocketContext} from "@/context/WebSocketContext";
import {ThreeJSCanvas3d} from "@/components/viewport3d/ThreeJSCanvas3d";
export const Viewport3d = () => {
    const { latestFrontendPayload } = useWebSocketContext();

    return (
        <Box sx={{ display: "flex", flexDirection: "column", height: "81vh" }}>

            <ThreeJSCanvas3d />

        </Box>
    );
}
