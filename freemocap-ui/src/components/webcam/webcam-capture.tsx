import {Box} from "@mui/system";
import React, {useState} from "react";
import Webcam from "react-webcam";
import useMediaRecorder from "@wmik/use-media-recorder";
import {Chunk} from "../../services/Record";

interface Props {
  device: MediaDeviceInfo
}

export const WebcamCapture = (props: Props) => {
  const {device} = props
  const [dataAvailable, setDataAvailable] = useState<Chunk[]>([]);
  const {startRecording, status} = useMediaRecorder({
    onDataAvailable: (blob) => {
      const newArray = [...dataAvailable];
      newArray.push({frameData: blob, timestamp: Date.now()} as Chunk);
      setDataAvailable(newArray)
      console.log(newArray)
    },
    // blobOptions: {"type": "video\/mp4"},
    // onError: e => {
    //   console.log(e)
    // },
    mediaStreamConstraints: {
      // video: true
      video: {
        deviceId: device.deviceId
      }
    }
  });

  if (status === "idle") {
    console.log('start recording')
    startRecording(16.67)
  }

  return (
    <Box>
      {device.label || `Device ${device.deviceId}`}
      <Webcam audio={true} videoConstraints={{deviceId: device.deviceId}} />
    </Box>
  );
};