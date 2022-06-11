import {Box} from "@mui/material";
import React, {useState} from "react";
import {useAsync} from "react-use";
import axios from "axios";
import {WebcamCapture} from "../../components/webcam/webcam-capture";

export const usePythonCameraDetection = () => {
  const [webcamIds, setWebcamIds] = useState();
  const response = useAsync(async () => {
    const response = await axios.get('http://localhost:8080/camera/detect');
    const webcamIds = response.data.cameras_found_list.map(x => x.webcam_id);
    setWebcamIds(webcamIds)
  }, [])
  return [webcamIds, response];
}

export const SetupAndPreviewView = () => {
  const [devices, setDevices] = useState<MediaDeviceInfo[]>();
  useAsync(async () => {
    const devices = await navigator.mediaDevices.enumerateDevices()
    const videoDevices = devices.filter(({ kind }) => kind.toLowerCase() === "videoinput")
    setDevices(videoDevices)
  }, [])
  return (
    <Box>
      {devices?.map(dev => {
        return <WebcamCapture device={dev} />
      })}
    </Box>
  )
}