import {useCallback, useEffect, useState} from 'react';
import {z} from 'zod';
import {FrontendFramePayloadSchema, JpegImagesSchema, Points3dSchema} from "@/models/FrontendFramePayloadSchema";
import {SkellyCamAppStateSchema} from "@/models/SkellyCamAppStateSchema";

const MAX_RECONNECT_ATTEMPTS = 20;

export const useWebSocket = (wsUrl: string) => {
    const [isConnected, setIsConnected] = useState(false);
    const [latestFrontendPayload, setLatestFrontendPayload] = useState<z.infer<typeof FrontendFramePayloadSchema> | null>(null);
    const [latestSkellyCamAppState, setLatestSkellyCamAppState] = useState<z.infer<typeof SkellyCamAppStateSchema> | null>(null);
    const [latestImages, setLatestImages] = useState<z.infer<typeof JpegImagesSchema> | null>(null);
    const [latestPoints3d, setLatestPoints3d] = useState<z.infer<typeof Points3dSchema> | null>(null);

    const [websocket, setWebSocket] = useState<WebSocket | null>(null);
    const [connectAttempt, setConnectAttempt] = useState(0);

    const handleIncomingMessage = (data: Blob | string) => {
        if (typeof data === 'string') {
            parseAndValidateMessage(data);
        } else if (data instanceof Blob) {
            // If data is a Blob, convert it to text
            data.text().then(text => {
                parseAndValidateMessage(text);
            }).catch(error => {
                console.error('Error reading Blob data:', error);
            });
        }
    };

    const parseAndValidateMessage = (data: string) => {
        try {
            const parsedData = JSON.parse(data);

            if (parsedData.type === 'FrontendFramePayload') {
                const frontendImagePayload = FrontendFramePayloadSchema.parse(parsedData);
                setLatestFrontendPayload(frontendImagePayload);
                setLatestImages(frontendImagePayload.jpeg_images);
                setLatestPoints3d(frontendImagePayload.points3d);
            } else if (parsedData.type === 'SkellycamAppStateDTO') {
                const skellycamAppState = SkellyCamAppStateSchema.parse(parsedData);
                setLatestSkellyCamAppState(skellycamAppState);
            } else {
                console.warn('Received unknown message type:', parsedData.type);
            }
        } catch (e) {
            if (e instanceof z.ZodError) {
                console.error('Validation failed with errors:', JSON.stringify(e.errors, null, 2));
            } else {
                console.error('Error parsing message data:', e);
            }
        }
    };


    const connect = useCallback(() => {
        if (websocket && websocket.readyState !== WebSocket.CLOSED) {
            return;
        }
        if (connectAttempt >= MAX_RECONNECT_ATTEMPTS) {
            console.error(`Max reconnection attempts reached. Could not connect to ${wsUrl}`);
            return;
        }
        const ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            setIsConnected(true);
            setConnectAttempt(0);
            console.log(`Websocket is connected to url: ${wsUrl}`)
        };

        ws.onclose = () => {
            setIsConnected(false);
            setConnectAttempt(prev => prev + 1);
        };

        ws.onmessage = (event) => {
            // console.log('Websocket message received with length: ', event.data.length);
            handleIncomingMessage(event.data);
        };

        ws.onerror = (error) => {
            console.error('Websocket error:', error);
        };

        setWebSocket(ws);
    }, [wsUrl, websocket, connectAttempt]);

    const disconnect = useCallback(()=>{
        if (websocket) {
            websocket.close();
            setWebSocket(null);
        }
    }, [websocket]);

    useEffect(() => {
        const timeout = setTimeout(() => {
            console.log(`Connecting (attempt #${connectAttempt+1} of ${MAX_RECONNECT_ATTEMPTS}) to websocket at url: ${wsUrl}`);
            connect();
        }, Math.min(1000 * Math.pow(2, connectAttempt), 30000)); // exponential backoff

        return () => {
            clearTimeout(timeout);
        };
    }, [connect]);

    return {isConnected, latestFrontendPayload, latestImages, latestPoints3d, latestSkellyCamAppState ,connect, disconnect};
};
