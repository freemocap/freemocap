export type OnMessageHandler = (ev: MessageEvent<Blob>, data_url: string) => Promise<void>;

export enum CaptureType {
  BoardDetection = "board_detection", SkeletonDetection = "skeleton_detection", Preview = "preview"
}

export class FrameCapture {
  private _ws_connection!: WebSocket;
  private readonly _host: string;
  private readonly _base_host: string = "ws://localhost:8080/ws";
  private readonly _revokeQueue: string[] = [];

  constructor(
    private readonly _webcamId: string,
    private readonly _captureType: CaptureType = CaptureType.BoardDetection,
  ) {
    this._host = `${this._base_host}/${this._captureType}/${this._webcamId}`
  }

  public get isConnectionClosed(): boolean {
    return this._ws_connection.readyState === this._ws_connection.CLOSED;
  }

  public start_frame_capture(onMessageHandler: OnMessageHandler) {
    this._ws_connection = new WebSocket(this._host);

    this._ws_connection.onopen = async () => {
      this._check_and_revoke();
    }

    this._ws_connection.onmessage = async (ev: MessageEvent<Blob>) => {
      const new_data_url = URL.createObjectURL(ev.data);
      await onMessageHandler(ev, new_data_url);
      this._revokeQueue.push(new_data_url);
    }

    this._ws_connection.onclose = async () => {
      this._full_revoke();
    }
  }

  public cleanup() {
    this._ws_connection.close();
  }

  private _check_and_revoke() {
    if (this._revokeQueue.length > 100) {
      const first50Images = this._revokeQueue.splice(0, 50);
      first50Images.forEach((imgUrl) => {
        URL.revokeObjectURL(imgUrl);
      })
    }
  }

  private _full_revoke() {
    this._revokeQueue.forEach((imgUrl) => {
      URL.revokeObjectURL(imgUrl);
    });
  }

}

