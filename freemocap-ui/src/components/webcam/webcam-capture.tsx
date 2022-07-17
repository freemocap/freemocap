import React, {useEffect, useState} from "react";
import {useDeviceStream} from "../../hooks/use-device-stream";
import {Capture} from "../../services/Capture";
import {Button} from "@mui/material";

interface Props {
  device: MediaDeviceInfo
}

export const WebcamCapture = (props: Props) => {
  const {device} = props
  const videoRef = React.useRef<HTMLVideoElement>(null);
  const stream = useDeviceStream(device)
  // const { sendMessage, getWebSocket } = useWebSocket("ws://localhost:8080/ws/hello_world")
  const [capture, setCapture] = useState<Capture>()
  useEffect(() => {
    const {current} = videoRef
    if (current) {
      // @ts-ignore
      current.srcObject = stream
      const capture = new Capture(videoRef)
      setCapture(capture)
    }
  }, [stream, videoRef])

  if (!stream) {
    return null
  }
  return (
    <>
      <video ref={videoRef} height={600} width={800} autoPlay />
      <canvas id={"canvasOutput"} />
      <Button onClick={() => {
        capture?.processVideo()
      }}>Start Capture</Button>
    </>
  );
};