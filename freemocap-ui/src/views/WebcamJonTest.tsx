import Webcam from "react-webcam";
import {BrowserCam} from "../services/cam";
import {useAsync, useMount} from "react-use";
import React from "react";
import { Box } from "@mui/material";

const cams = new BrowserCam().findAllCameras();

export const WebcamJonTest = () => {
  useAsync(async () => {
    const cams = await new BrowserCam().findAllCameras();
    console.log(cams);
  }, []);
  const cst = navigator.mediaDevices.getSupportedConstraints()

  const constraints: MediaStreamConstraints = {
    video: {
      // Jon, you can change stuff here

      // You can select a specific video device by putting a device Id here.
      // Check your browser console to take a device you'd like.
      // deviceId: "",

      exposureMode: "manual",
      exposureCompensation: "-3"
    }  as any
  }



  return (
    <Box>
      <Webcam videoConstraints={constraints.video}/>
      <Box>

      </Box>
    </Box>
  )
}