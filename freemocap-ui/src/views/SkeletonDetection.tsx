import React from "react";
import {Box} from "@mui/material";
import {CaptureType, useFrameCapture} from "../services/frame-capture";

export const SkeletonDetection = () => {
  const [frameCapture, data] = useFrameCapture("0", CaptureType.SkeletonDetection);

  if (!data) {
    return null;
  }
  return (
    <Box>
      {!frameCapture.isConnectionClosed && <img src={frameCapture.current_data_url} alt={"video capture"}/>}
    </Box>
  );
}