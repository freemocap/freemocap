import {useEffect, useState} from "react";

type OnMessageHandler = (ev: MessageEvent<Blob>, data_url: string) => Promise<void>;

export enum CaptureType {
  BoardDetection = "board_detection",
  SkeletonDetection = "skeleton_detection",
}

export class FrameCapture {
  private _ws_connection!: WebSocket;
  private readonly _host: string;
  private readonly _base_host: string = "ws://localhost:8080/ws";

  constructor(
    private readonly _webcamId: string,
    private readonly _captureType: CaptureType = CaptureType.BoardDetection,
  ) {
    this._host = `${this._base_host}/${this._captureType}/${this._webcamId}`
  }

  private _current_data_url: string = ""

  public get current_data_url(): string {
    return this._current_data_url;
  }

  public get isConnectionClosed(): boolean {
    return this._ws_connection.readyState === this._ws_connection.CLOSED;
  }

  public start_frame_capture(onMessageHandler: OnMessageHandler) {
    this._ws_connection = new WebSocket(this._host);
    this._ws_connection.onmessage = async (ev: MessageEvent<Blob>) => {
      if (this._current_data_url) {
        URL.revokeObjectURL(this._current_data_url);
      }
      const new_data_url = URL.createObjectURL(ev.data);
      this._current_data_url = new_data_url;
      await onMessageHandler(ev, new_data_url);
    }
  }

  public cleanup() {
    this._ws_connection.close();
  }
}


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