import {useEffect, useState} from "react";
import {CaptureType, FrameCapture, OnMessageHandler} from "../services/frame-capture";

export const useFrameCapture = ( captureType: CaptureType, port:number, onMessage?: OnMessageHandler): [FrameCapture, string] => {
  const [webcam_id] = useState<string>("0");
  const [frameCapture,] = useState(() => new FrameCapture( captureType, port));

  const [data, setDataUrl] = useState<string>("");

  useEffect(() => {
    frameCapture.start_frame_capture(async (ev: MessageEvent<Blob>, data_url: string) => {
      setDataUrl(data_url);
      if (onMessage) {
        await onMessage(ev, data_url);
      }
    });
    return () => {
      frameCapture.cleanup()
    }
  }, [webcam_id]);

  window.onbeforeunload = () => {
    frameCapture.cleanup()
  }

  return [frameCapture, data];
}
