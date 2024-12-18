import {Box, Button} from "@mui/material";
import React from "react";
import {ConnectToCamerasButton} from "@/components/ConnectToCamerasButton";
import {useWebSocketContext} from "@/context/WebSocketContext";

export const PythonCamerasView = () => {
    const { latestFrontendPayload } = useWebSocketContext();

    return (
        <Box sx={{ display: "flex", flexDirection: "column" }}>
            <ConnectToCamerasButton />
            {latestFrontendPayload && latestFrontendPayload.jpeg_images && (
                <Box sx={{ display: "flex", flexDirection: "row", flexWrap: "wrap" }}>
                    {Object.entries(latestFrontendPayload.jpeg_images).map(([cameraId, base64Image]) => (
                        base64Image ? (
                            <img
                                key={cameraId}
                                src={`data:image/jpeg;base64,${base64Image}`}
                                alt={`Camera ${cameraId}`}
                                style={{ width: "200px", height: "auto", margin: "10px" }} // Adjust size as needed
                            />
                        ) : null
                    ))}
                </Box>
            )}
        </Box>
    );
}
