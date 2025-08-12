import {useCallback, useEffect, useRef, useState} from "react";
import {useAppDispatch} from "@/store/AppStateStore";
import {
    FrameRenderAcknowledgment,
    useWebsocketBinaryMessageProcessor
} from "@/context/websocket-context/useWebsocketBinaryMessageProcessor";
import {setBackendFramerate, setFrontendFramerate} from "@/store/slices/framerateTrackerSlice";
import {FramerateUpdateWebSocketMessage, WebSocketMessageSchema} from "@/context/websocket-context/websocket-types";
import {addLog} from "@/store/slices/logRecordsSlice";


export const useWebSocket = (wsUrl: string) => {
    const [isConnected, setIsConnected] = useState(false);
    const [websocket, setWebSocket] = useState<WebSocket | null>(null);
    const [connectAttempt, setConnectAttempt] = useState(0);
    const dispatch = useAppDispatch();
    const {
        processBinaryMessage,
        latestImageData,
    } = useWebsocketBinaryMessageProcessor();
    const latestFrameAcknowledgment = useRef<FrameRenderAcknowledgment | null>(null);
    const latestCameraFrameAcknowledgment = useRef<Record<string, number>>({});

    // Handler for framerate update messages
    const handleFramerateUpdate = useCallback((message: FramerateUpdateWebSocketMessage) => {
        dispatch(setBackendFramerate(message.backend_framerate));
        dispatch(setFrontendFramerate(message.frontend_framerate));

    }, [dispatch]);

    // handler frame render acknowledgment messages
    const acknowledgeFrameRendered = useCallback(
        (cameraId: string, frameNumber: number) => {
            latestCameraFrameAcknowledgment.current[cameraId] = frameNumber;
            const allAcknowledged = Object.values(latestCameraFrameAcknowledgment.current).every(
                (acknowledgedFrame) => acknowledgedFrame === latestFrameAcknowledgment.current?.frameNumber);

            if (allAcknowledged && latestFrameAcknowledgment.current) {
                // Schedule the acknowledgment to be sent on the next frame
                setTimeout(() => {
                    websocket?.send(
                        JSON.stringify(latestFrameAcknowledgment.current)
                    );
                }, 0);
            }
        },
        [latestCameraFrameAcknowledgment, latestFrameAcknowledgment, websocket]
    )
    // Process JSON messages with type discrimination
    const processJsonMessage = useCallback((jsonData: unknown) => {
        try {
            // Now validate against the full message schema
            const result = WebSocketMessageSchema.safeParse(jsonData);
            if (!result.success) {
                throw new Error("Invalid base message format: " + result.error.message);

            }

            const message = result.data;

            // Handle different message types
            switch (message.message_type) {
                case "framerate_update":
                    handleFramerateUpdate(message);
                    break;
                case "log_record":
                    // Add the log record to the Redux store
                    dispatch(addLog(message));
                    break;
                default:
                    console.log(`Received websocket message of unknown type: ${message}`);
            }
        } catch (error) {
            console.error(`Error processing JSON message:${error}\n\nData:`, jsonData);

        }
    }, [handleFramerateUpdate]);

    const handleIncomingMessage = useCallback(
        async (event: MessageEvent, ws: WebSocket) => {
            const data = event.data;

            // Handle binary data
            if (data instanceof ArrayBuffer) {
                latestFrameAcknowledgment.current = await processBinaryMessage(data);
            } else if (typeof data === "string") {
                if (data === 'ping') {
                    console.log("Received ping message, sending pong response");
                    ws.send("pong");
                    return;
                }

                try {
                    const jsonData = JSON.parse(data);
                    processJsonMessage(jsonData);
                } catch (error) {
                    console.log("Received non-JSON string data:", data);
                }
            } else {
                console.warn("Received unsupported message type:", typeof data);
            }
        },
        [processBinaryMessage, processJsonMessage]
    );

    const connect = useCallback(() => {
        if (websocket && websocket.readyState !== WebSocket.CLOSED) {
            return;
        }

        const ws = new WebSocket(wsUrl);
        ws.binaryType = "arraybuffer";

        ws.onopen = () => {
            setIsConnected(true);
            setConnectAttempt(0);
            ws.send("Hello from the Skellycam Frontend💀📸👋");
            console.log(`Websocket is connected to url: ${wsUrl}`);
        };

        ws.onclose = () => {
            setIsConnected(false);
            setConnectAttempt((prev) => prev + 1);
        };

        ws.onmessage = (event) => {
            handleIncomingMessage(event, ws).then(
                () => {
                }
            ).catch((error) => {
                    console.error("Error processing incoming message:", error);
                }
            );
        };

        ws.onerror = (error) => {
            console.error("Websocket error:", error);
        };
        setWebSocket(ws);
    }, [wsUrl, websocket, connectAttempt]);

    const disconnect = useCallback(() => {
        if (websocket) {
            websocket.close();
            setWebSocket(null);
        }
    }, [websocket]);

    useEffect(() => {
        const timeout = setTimeout(() => {
            console.log(
                `Connecting  to websocket at url: ${wsUrl} (attempt #${connectAttempt + 1})`
            );
            connect();
        }, Math.min(1000 * Math.pow(2, connectAttempt), 10000)); // exponential backoff

        return () => {
            clearTimeout(timeout);
        };
    }, [connect, connectAttempt, wsUrl]);

    return {
        isConnected,
        connect,
        disconnect,
        latestCameraData: latestImageData,
        acknowledgeFrameRendered,
    };
};
