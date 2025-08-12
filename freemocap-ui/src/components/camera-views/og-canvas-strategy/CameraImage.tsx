import { Box, Typography } from "@mui/material";
import React, { useRef, useEffect } from "react";
import { CameraImageData } from "@/context/websocket-context/useWebsocketBinaryMessageProcessor";
import { useWebSocketContext } from "@/context/websocket-context/WebSocketContext";

interface CameraImageProps {
  cameraImageData: CameraImageData;
}

export const CameraImage = ({ cameraImageData }: CameraImageProps) => {
  const { cameraId, imageBitmap, imageWidth, imageHeight, cameraIndex, frameNumber } = cameraImageData;
  const { acknowledgeFrameRendered } = useWebSocketContext();
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const renderImage = async () => {
      const canvas = canvasRef.current;
      if (!canvas || !imageBitmap) return;

      // Set canvas dimensions if needed
      if (canvas.width !== imageWidth || canvas.height !== imageHeight) {
        canvas.width = imageWidth;
        canvas.height = imageHeight;
      }

      try {
        const ctx = canvas.getContext('2d');
        if (ctx) {
          ctx.drawImage(imageBitmap, 0, 0);
          acknowledgeFrameRendered(cameraId, frameNumber);
        }
      } catch (error) {
        console.error("Error rendering camera image:", error);
      }
    };

    renderImage();
  }, [cameraId, imageBitmap, imageWidth, imageHeight, frameNumber, acknowledgeFrameRendered]);

  return (
    <Box
      key={cameraId}
      sx={{
        position: 'relative',
      }}
    >
      <canvas
        ref={canvasRef}
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
