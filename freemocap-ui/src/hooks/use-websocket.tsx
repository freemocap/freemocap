import {useEffect, useState} from "react";
import {CaptureType, WebsocketConnection, OnMessageHandler} from "../services/websocket-connection";

export const useWebsocket = (captureType: CaptureType,
                             port: number,
                             onMessage?: OnMessageHandler): [WebsocketConnection, { [key: string]: string }] => {

    const [webcam_id] = useState<string>("0");
    const [websocketConnection,] = useState(() => new WebsocketConnection(captureType, port));

    const [dataUrls, setDataUrls] = useState<{ [key: string]: string }>({});

    useEffect(() => {
        websocketConnection.connect_to_cameras(async (ev: MessageEvent<Blob>, data_urls: { [key: string]: string }) => {
            setDataUrls(data_urls as { [key: string]: string });
            if (onMessage) {
                await onMessage(ev, data_urls);
            }
        });
        return () => {
            websocketConnection.cleanup()
        }
    }, [websocketConnection, onMessage, webcam_id]);

    window.onbeforeunload = () => {
        websocketConnection.cleanup()
    }

    return [websocketConnection, dataUrls];
}
