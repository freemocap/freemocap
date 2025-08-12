import { Box, Button, ButtonGroup, FormControlLabel, Switch, Typography } from "@mui/material";
import React, {useEffect, useMemo, useRef, useState} from "react";
import {CameraImage} from "@/components/camera-views/og-canvas-strategy/CameraImage";
import { CameraImageData } from "@/context/websocket-context/useWebsocketBinaryMessageProcessor";
import {useCameraGridLayout} from "@/hooks/useCameraGridLayout";
import {useWebSocketContext} from "@/context/websocket-context/WebSocketContext";

// Utility function to debounce function calls
const debounce = (fn: Function, ms = 50) => {
    let timeoutId: ReturnType<typeof setTimeout>;
    return function(...args: any[]) {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => fn(...args), ms);
    };
};

export const CameraImagesGrid = () => {
    const {latestCameraData} = useWebSocketContext();

    return (
        <Box sx={{ height: '100%',
            width: '100%',
            display: 'flex',
            flexDirection: 'row',
            flexWrap: 'wrap',
        }}>

            {Object.entries(latestCameraData).map(([cameraId, cameraImageData]) =>
                cameraImageData ? (
                    <CameraImage
                        key={cameraId}
                        cameraImageData={cameraImageData}
                    />
                ) : null
            )}
        </Box>
    );
};
