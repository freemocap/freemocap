import { Box } from "@mui/material";
import React from "react";
import {CameraImage} from "@/components/camera-views/CameraImage";

interface CameraImagesGridProps {
    images: { [cameraId: string]: string };
    showAnnotation: boolean;
}

export const CameraImagesGrid = ({ images, showAnnotation }: CameraImagesGridProps) => {
    return (
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
            {Object.entries(images).map(([cameraId, base64Image]) =>
                base64Image ? (
                    <CameraImage key={cameraId} cameraId={cameraId} base64Image={base64Image} showAnnotation={showAnnotation} />
                ) : null
            )}
        </Box>
    );
};
