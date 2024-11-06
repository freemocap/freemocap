export type OnMessageHandler = (ev: MessageEvent<Blob>, data_urls: { [key: string]: string }) => Promise<void>;

export enum CaptureType {
    BoardDetection = "board_detection", SkeletonDetection = "skeleton_detection", ConnectCameras = "connect"
}

export class FrameCapture {
    private _ws_connection!: WebSocket;
    private readonly _host: string;
    private readonly _base_host: string;

    constructor(private readonly _captureType: CaptureType = CaptureType.BoardDetection,
                private readonly _port: number = 8005) {
        this._base_host = `ws://localhost:${_port}/websocket`;
        this._host = `${this._base_host}/${this._captureType}`
        console.log(`FrameCapture : ${this._host}`)
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
        const decoder = new TextDecoder('utf-8');
        this._ws_connection = new WebSocket(this._host);

        this._ws_connection.onmessage = async (ev: MessageEvent<Blob>) => {
            // Ensure the event.data is a Blob
            if (ev.data instanceof Blob) {
                // Convert the incoming data to an ArrayBuffer
                const arrayBuffer = await ev.data.arrayBuffer();

                // Convert ArrayBuffer to a string
                const jsonString = decoder.decode(arrayBuffer);

                // Parse the JSON string to a JavaScript object
                const data = JSON.parse(jsonString);
                console.log(`Received message with length: ${jsonString.length} from mf_payload# ${data.multi_frame_number}`);
                const jpegImagesByCamera = data.jpeg_images;

                // Iterate over the framesObject to create a data URL for each image
                const dataUrls: { [key: string]: string } = {};
                for (const [cameraId, jpegImage] of Object.entries(jpegImagesByCamera) as [string, Uint8Array][]) {
                    const blob = new Blob([jpegImage], { type: 'image/jpeg' });
                    dataUrls[cameraId] = URL.createObjectURL(blob);
                }

                // Call the onMessageHandler with the dataUrls object
                await onMessageHandler(ev, dataUrls);


            } else {
                console.log(`Received message with length: ${JSON.stringify(ev.data)}`);
            }
        };





    }

    public cleanup() {
        this._ws_connection.close();
    }
}

