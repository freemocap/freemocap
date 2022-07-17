import {useEffect, useState} from "react";
import {CaptureType, FrameCapture, OnMessageHandler} from "../services/frame-capture";

export const useFrameCapture = (webcam_id: string, captureType: CaptureType, onMessage?: OnMessageHandler): [FrameCapture, string] => {
  const [frameCapture,] = useState(() => new FrameCapture(webcam_id, captureType));
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