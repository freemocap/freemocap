import {Box} from "@mui/material";
import {useFrameCapture} from "../hooks/use-frame-capture";
import {CaptureType} from "../services/frame-capture";
import React from "react";

export const ShowCameras = () => {

  const [frameCapture, data] = useFrameCapture(CaptureType.ConnectCameras, 8003);
  if (!data) {
    return null;
  }
  return (
    <Box>
      {!frameCapture.isConnectionClosed && <img src={frameCapture.current_data_url} alt={"video capture"}/>}
    </Box>
  );
}
