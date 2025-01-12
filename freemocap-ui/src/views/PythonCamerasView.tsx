import {Box, Button} from "@mui/material";
import React from "react";
import {ConnectToCamerasButton} from "@/components/ConnectToCamerasButton";
import {useWebSocketContext} from "@/context/WebSocketContext";
import {ThreeJSCanvas3d} from "@/components/viewport3d/ThreeJSCanvas3d";
export const PythonCamerasView = () => {
    const { latestFrontendPayload } = useWebSocketContext();

    return (
        <Box sx={{ display: "flex", flexDirection: "column", height: "70vh" }}>
            {latestFrontendPayload && latestFrontendPayload.jpeg_images && (
                <Box
                    sx={{
                        display: "flex",
                        flexDirection: "row",
                        flexWrap: "wrap",
                        flexGrow: 1,
                        justifyContent: "center",
                        alignItems: "center",
                        overflow: "hidden"
                    }}
                >
                    {Object.entries(latestFrontendPayload.jpeg_images).map(([cameraId, base64Image]) => (
                        base64Image ? (
                            <Box
                                key={cameraId}
                                sx={{
                                    display: "flex",
                                    justifyContent: "center",
                                    alignItems: "center",
                                    flexBasis: "calc(50% - 5px)",
                                    margin: "1px",
                                    boxSizing: "border-box"
                                }}
                            >
                                <img
                                    src={`data:image/jpeg;base64,${base64Image}`}
                                    alt={`Camera ${cameraId}`}
                                    style={{
                                        width: "100%",
                                        height: "auto",
                                        maxHeight: "100%",
                                        objectFit: "contain"
                                    }}
                                />
                            </Box>
                        ) : null
                    ))}
                </Box>
            )}


        </Box>
    );
}
