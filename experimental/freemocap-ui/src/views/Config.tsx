import {Box, Typography} from "@mui/material";
import React from "react";
import {useAsync} from "react-use";
import {BrowserCam} from "../services/cam";

export const ConfigView = () => {
  const [Container] = [Box, Box];
  const [devices, setDevices] = React.useState<MediaDeviceInfo[]>([]);
  useAsync(async () => {
    const cam = new BrowserCam();
    const deviceInfos = await cam.findAllCameras();
    setDevices(deviceInfos)
  });
  const devicesWithNames = devices.filter(x => x.label);
  return (
    <Container>
      <Typography>Configuration</Typography>
      {devicesWithNames
        .map(device => {
        return (
          <Typography>Webcam {device.label}</Typography>
        )
      })}
    </Container>
  )
}