import {decode} from "@msgpack/msgpack";

export type OnMessageHandler = (ev: MessageEvent<Blob>, data_urls: object) => Promise<void>;

export enum CaptureType {
    BoardDetection = "board_detection", SkeletonDetection = "skeleton_detection", ConnectCameras = "connect"
}

export class FrameCapture {
    private _ws_connection!: WebSocket;
    private readonly _host: string;
    private readonly _base_host: string;


    constructor(private readonly _captureType: CaptureType = CaptureType.BoardDetection,
                private readonly _port: number = 8000) {
        this._base_host = `ws://localhost:${_port}/ws`;
        this._host = `${this._base_host}/${this._captureType}`
        console.log(`FrameCapture: ${this._host}`)
    }

    private _current_data_url!: string;

    public get current_data_url(): string {
        return this._current_data_url;
    }

    public get isConnectionClosed(): boolean {
        return this._ws_connection ? this._ws_connection.readyState === this._ws_connection.CLOSED : true;
    }
    public start_frame_capture(onMessageHandler: OnMessageHandler) {
        console.log(`FrameCapture: start_frame_capture: ${this._host}`)
        this._ws_connection = new WebSocket(this._host);
        this._ws_connection.onmessage = async (ev: MessageEvent<Blob>) => {
            console.debug(`FrameCapture: onmessage - received data: ${ev.data.size} bytes`);

            // Read the Blob as an ArrayBuffer
            const arrayBuffer = await ev.data.arrayBuffer();

            // Decode the MessagePack data into a JavaScript object
            const framesObject = decode(new Uint8Array(arrayBuffer)) as { [key: string]: Uint8Array };
            // Iterate over the framesObject to create a data URL for each image
            const dataUrls = {};
            for (const [cameraId, imageBytes] of Object.entries(framesObject)) {
                const blob = new Blob([imageBytes], { type: 'image/jpeg' });
                dataUrls[cameraId] = URL.createObjectURL(blob);
            }

            // Call the onMessageHandler with the dataUrls object
            await onMessageHandler(ev, dataUrls);
        }
    }

    public cleanup() {
        this._ws_connection.close();
    }
}

