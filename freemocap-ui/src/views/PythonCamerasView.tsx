import { Box, Button } from "@mui/material";
import React, { useState, useEffect } from "react";
import { useWebSocketContext } from "@/context/WebSocketContext";
import {CameraImagesGrid} from "@/components/camera-views/CameraImagesGrid";


export const PythonCamerasView = () => {
    const {latestImages} = useWebSocketContext();
    const [showAnnotation, setShowAnnotation] = useState(true);
    const toggleAnnotation = () => {
        setShowAnnotation(prev => !prev);
    };

    useEffect(() => {
        const handleKeyDown = (event: KeyboardEvent) => {
            if (event.key === 'a') {
                toggleAnnotation();
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => {
            window.removeEventListener('keydown', handleKeyDown);
        };
    }, []);

    return (
        <Box sx={{ display: "flex", flexDirection: "column", height: "70vh" }}>
            {latestImages  && (
                <CameraImagesGrid images={latestImages} showAnnotation={showAnnotation} />
            )}
        </Box>
    );
};
