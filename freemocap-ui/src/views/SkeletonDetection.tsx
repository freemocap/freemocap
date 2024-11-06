import React from "react";
import {Box} from "@mui/material";
import {CaptureType} from "../services/frame-capture";
import {useFrameCapture} from "../hooks/use-frame-capture";

export const SkeletonDetection = () => {
    const [frameCapture, data] = useFrameCapture(CaptureType.SkeletonDetection, 8080,);
    if (!data) {
        return null;
    }
    return (
        <Box>
            {!frameCapture.isConnectionClosed && <img src={frameCapture.current_data_url} alt={"video capture"}/>}
        </Box>
    );
}
