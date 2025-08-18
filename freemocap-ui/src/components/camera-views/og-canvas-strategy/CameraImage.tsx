import { Box, Typography } from "@mui/material";
import React, { useRef, useMemo } from "react";
import { CameraImageData } from "@/context/websocket-context/useWebsocketBinaryMessageProcessor";
import {useWebSocketContext} from "@/context/websocket-context/WebSocketContext";

interface CameraImageProps {
    cameraImageData: CameraImageData;
}

export const CameraImage = ({ cameraImageData}: CameraImageProps) => {
    const { cameraId, imageBitmap, imageWidth, imageHeight, cameraIndex , frameNumber} = cameraImageData;
    const {acknowledgeFrameRendered} = useWebSocketContext()
    const canvasRef = useRef<HTMLCanvasElement>(null);

    // Directly render the bitmap when the ref callback is called
    const setCanvasRef = (canvas: HTMLCanvasElement | null) => {

        if (canvas && imageBitmap) {
            const ctx = canvas.getContext('2d');
            if (ctx) {
                canvas.width = imageWidth;
                canvas.height = imageHeight;
                ctx.drawImage(imageBitmap, 0, 0);
                acknowledgeFrameRendered(cameraId, frameNumber);
            }
        }
    };

    return (
        <Box
            key={cameraId}
            sx={{
                position: 'relative',
                border: "1px solid #333",
            }}
        >
            <canvas
                ref={setCanvasRef}
                style={{
                    objectFit: 'cover',
                }}
            />
                <Typography
                    variant="caption"
                    sx={{
                        position: "absolute",
                        bottom: 8,
                        left: 8,
                        color: "white",
                        backgroundColor: "rgba(0, 0, 0, 0.5)",
                        padding: "2px 4px",
                        borderRadius: "4px",
                        zIndex: 1,
                    }}
                >
                    Camera {cameraIndex}
                </Typography>

        </Box>
    );
};
