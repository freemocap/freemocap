import {Box} from "@mui/material";
import React, {useState} from "react";
import Webcam from "react-webcam";
import {useAsync} from "react-use";
import {StartStopProcess} from "../components/start-stop-process";
import {BrowserCam} from "../services/cam";
import {StreamByDeviceId} from "../services/recorder";

class ViewState {
  public deviceInfos: MediaDeviceInfo[] = [];
  public streams!: StreamByDeviceId;
}

export const WebcamStreamCapture = () => {
  const [devices, setDevices] = useState<ViewState>(() => new ViewState());
  // grab all devices
  useAsync(async () => {
    const cam = new BrowserCam();
    const devices = await cam.findAllCameras();
    setDevices(prev => {
      return {
        ...prev,
        deviceInfos: devices
      };
    });
  }, []);

  return (
    <Box>
      <Box>
        {devices.deviceInfos.map(dev => {
          return (
            <Webcam audio={false} videoConstraints={{deviceId: dev.deviceId}} onUserMedia={stream => {
              setDevices(prev => {
                return {
                  ...prev,
                  streams: {
                    ...prev.streams,
                    [dev.deviceId]: stream
                  }
                };
              });
            }} />
          )
        })}
      </Box>
      {devices.streams ? <StartStopProcess streams={devices.streams} /> : <></>}

    </Box>
  );
};
