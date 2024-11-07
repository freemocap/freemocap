import {Box} from "@mui/material";
import {useWebsocket} from "@/hooks/use-websocket";
import {CaptureType} from "@/services/websocket-connection";
import React from "react";

export const PythonCamerasView = () => {

  const [websocketConnection, dataUrls] = useWebsocket(CaptureType.ConnectCameras, 8005);
  if (!dataUrls) {
    return null;
  }
  return (
      <Box sx={{display: "flex", flexDirection: "column"}}>
        Hi wowowwwee
        websocket status: {websocketConnection.isConnectionClosed ? "closed" : "open"}
        {!websocketConnection.isConnectionClosed && Object.entries(dataUrls).map(([cameraId, url]) => (
            <img key={cameraId} src={url} alt={`video capture from camera ${cameraId}`}/>
        ))}
    </Box>
  );
}
