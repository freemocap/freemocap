import {useEffect, useState} from "react";
import {CaptureType, FrameCapture, OnMessageHandler} from "../services/frame-capture";

export const useFrameCapture = ( captureType: CaptureType, port:number, onMessage?: OnMessageHandler): [FrameCapture, {[key: string]: string}] => {
  const [webcam_id] = useState<string>("0");
  const [frameCapture,] = useState(() => new FrameCapture( captureType, port));

  const [data, setDataUrls] = useState<{[key: string]: string}>({});

  useEffect(() => {
    frameCapture.start_frame_capture(async (ev: MessageEvent<Blob>, data_urls: { [key: string]: string }) => {
      setDataUrls(data_urls as {[key: string]: string});
      if (onMessage) {
        await onMessage(ev, data_urls);
      }
    });
    return () => {
      frameCapture.cleanup()
    }
  }, [frameCapture, onMessage, webcam_id]);

  window.onbeforeunload = () => {
    frameCapture.cleanup()
  }

  return [frameCapture, data];
}
