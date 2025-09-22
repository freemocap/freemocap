import {Box} from "@mui/material";
import React from "react";
import {CameraImage} from "@/components/camera-views/og-canvas-strategy/CameraImage";
import {useWebSocketContext} from "@/context/websocket-context/WebSocketContext";


export const CameraImagesGrid = () => {
    const {latestImageData} = useWebSocketContext();

    return (
        <Box sx={{ height: '100%',
            width: '100%',
            display: 'flex',
            gap: 1,
            flexDirection: 'row',
            flexWrap: 'wrap',
        }}>

            {Object.entries(latestImageData).map(([cameraId, cameraImageData]) =>
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
