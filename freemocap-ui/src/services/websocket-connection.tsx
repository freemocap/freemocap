export type OnMessageHandler = (ev: MessageEvent<Blob>, data_urls: { [key: string]: string }) => Promise<void>;

export enum CaptureType {
    ConnectCameras = "connect"
}

export class WebsocketConnection {
    private _ws_connection!: WebSocket;
    private readonly _host_url: string;
    private readonly _base_host_url: string;

    constructor(private readonly _captureType: CaptureType = CaptureType.ConnectCameras,
                private readonly _port: number = 8005) {
        this._base_host_url = `ws://localhost:${_port}/websocket`;
        this._host_url = `${this._base_host_url}/${this._captureType}`
        console.log(`WebsocketConnection.constructor: ${this._host_url}`);
    }

    private _current_data_url!: string;

    public get current_data_url(): string {
        return this._current_data_url;
    }

    public get isConnectionClosed(): boolean {
        return this._ws_connection ? this._ws_connection.readyState === this._ws_connection.CLOSED : true;
    }
    public connect_to_cameras(onMessageHandler: OnMessageHandler) {
        console.log(`WebsocketConnection.connect_to_cameras, connecting to ${this._host_url}`);
        const decoder = new TextDecoder('utf-8');
        this._ws_connection = new WebSocket(this._host_url);

        this._ws_connection.onmessage = async (ev: MessageEvent<Blob>) => {
            // Ensure the event.data is a Blob
            if (ev.data instanceof Blob) {
                // Convert the incoming data to an ArrayBuffer
                const arrayBuffer = await ev.data.arrayBuffer();

                // Convert ArrayBuffer to a string
                const jsonString = decoder.decode(arrayBuffer);

                // Parse the JSON string to a JavaScript object
                const data = JSON.parse(jsonString);
                console.log(`Received message with length: ${jsonString.length} bytes, type: ${typeof data}`);
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
                console.log(`Received non-Blob message with length: ${JSON.stringify(ev.data)}, type: ${typeof ev.data}`);
            }
        };
    }

    public cleanup() {
        this._ws_connection.close();
    }
}

