import React, {createContext, ReactNode, useCallback, useContext, useEffect, useRef, useState} from 'react';
import {useDispatch} from 'react-redux';
import {AppDispatch} from '@/store/types';

import {ConnectionState, WebSocketConnection} from "@/services/server/server-helpers/websocket-connection";
import {FrameProcessor} from "@/services/server/server-helpers/frame-processor/frame-processor";
import {CanvasManager} from "@/services/server/server-helpers/canvas-manager";
import {serverUrls} from "@/services";
import {backendFramerateUpdated, DetailedFramerate, frontendFramerateUpdated, logAdded, LogRecord} from '@/store';
import {
    CharucoObservation,
    CharucoOverlayDataMessage,
    CharucoOverlayDataMessageSchema
} from "@/services/server/server-helpers/charuco_types";
import {FrameCompositor} from "@/services/server/server-helpers/frame_compositor";

type FrameSubscriber = (cameraId: string, bitmap: ImageBitmap) => void;


interface ServerContextValue {
    isConnected: boolean;
    connect: () => void;
    disconnect: () => void;
    send: (data: string | object) => void;
    setCanvasForCamera: (cameraId: string, canvas: HTMLCanvasElement) => void;
    getFps: (cameraId: string) => number | null;
    connectedCameraIds: string[];
    subscribeToFrames: (callback: FrameSubscriber) => () => void;
}

const ServerContext = createContext<ServerContextValue | null>(null);


function arraysEqual(a: string[], b: string[]): boolean {
    if (a.length !== b.length) return false;
    const sortedA = [...a].sort();
    const sortedB = [...b].sort();
    return sortedA.every((val, idx) => val === sortedB[idx]);
}

// Type guard to check if a message is a log record
function isLogRecord(data: any): data is LogRecord {
    return (
        data &&
        typeof data === 'object' &&
        data.message_type === 'log_record' &&
        typeof data.levelname === 'string' &&
        typeof data.message === 'string'
    );
}

// Type for framerate update message from backend
interface FramerateUpdateMessage {
    message_type: 'framerate_update';
    camera_group_id: string;
    backend_framerate: DetailedFramerate;
    frontend_framerate: DetailedFramerate;
}

// Type guard to check if a message is a framerate update
function isFramerateUpdate(data: any): data is FramerateUpdateMessage {
    return (
        data &&
        typeof data === 'object' &&
        data.message_type === 'framerate_update' &&
        typeof data.camera_group_id === 'string' &&
        data.backend_framerate &&
        typeof data.backend_framerate === 'object' &&
        data.frontend_framerate &&
        typeof data.frontend_framerate === 'object'
    );
}

// Type guard for CharucoOverlayDataMessage using Zod
function isCharucoOverlayDataMessage(data: any): data is CharucoOverlayDataMessage {
    const result = CharucoOverlayDataMessageSchema.safeParse(data);
    return result.success;
}

export const ServerContextProvider: React.FC<{ children: ReactNode }> = ({children}) => {
    const dispatch = useDispatch<AppDispatch>();

    // Reactive state - only updates when camera list actually changes
    const [isConnected, setIsConnected] = useState<boolean>(false);
    const [connectedCameraIds, setConnectedCameraIds] = useState<string[]>([]);

    // Service instances
    const wsConnectionRef = useRef<WebSocketConnection | null>(null);
    const frameProcessorRef = useRef<FrameProcessor | null>(null);
    const canvasManagerRef = useRef<CanvasManager | null>(null);
    const frameCompositorRef = useRef<FrameCompositor | null>(null);
    const frameSubscribersRef = useRef<Set<FrameSubscriber>>(new Set());

    // Store latest observation for each camera
    const latestObservationsRef = useRef<Map<string, CharucoObservation>>(new Map());

    // Initialize services once
    useEffect(() => {
        wsConnectionRef.current = new WebSocketConnection({
            url: serverUrls.getWebSocketUrl(),
            reconnectDelay: 1000,
            maxReconnectAttempts: 5,
            heartbeatInterval: 30000
        });
        frameProcessorRef.current = new FrameProcessor();
        canvasManagerRef.current = new CanvasManager();
        frameCompositorRef.current = new FrameCompositor();

        return () => {
            if (wsConnectionRef.current) {
                wsConnectionRef.current.disconnect();
            }
            if (canvasManagerRef.current) {
                canvasManagerRef.current.terminateAllWorkers();
            }
            if (frameProcessorRef.current) {
                frameProcessorRef.current.reset();
            }
            if (frameCompositorRef.current) {
                frameCompositorRef.current.destroy();
            }
            latestObservationsRef.current.clear();
        };
    }, []);

    // Set up WebSocket connection and handlers
    useEffect(() => {
        const ws = wsConnectionRef.current;
        if (!ws) return;

        const handleStateChange = (newState: ConnectionState): void => {
            const connected = newState === ConnectionState.CONNECTED;
            setIsConnected(connected);

            if (newState === ConnectionState.DISCONNECTED || newState === ConnectionState.FAILED) {
                canvasManagerRef.current?.terminateAllWorkers();
                frameProcessorRef.current?.reset();
                latestObservationsRef.current.clear();
                setConnectedCameraIds([]);
            }
        };

        const handleMessage = async (event: MessageEvent): Promise<void> => {
            // Handle binary frame data
            if (event.data instanceof ArrayBuffer) {
                try {
                    const result = await frameProcessorRef.current!.processFramePayload(event.data);
                    if (!result) return;

                    const {frames, cameraIds, frameNumbers} = result;

                    // Convert Set to sorted array for comparison
                    const currentCameraIds = Array.from(cameraIds).sort();
                    // Update state only if camera list has changed
                    setConnectedCameraIds(prevIds => {
                        if (!arraysEqual(prevIds, currentCameraIds)) {
                            console.log(`Camera list updated: ${currentCameraIds.join(', ')}`);

                            // Clean up workers for cameras that are no longer in the payload
                            const removedCameras = prevIds.filter(id => !cameraIds.has(id));
                            for (const cameraId of removedCameras) {
                                console.log(`Removing camera ${cameraId} - not in latest payload`);
                                canvasManagerRef.current?.terminateWorker(cameraId);
                                latestObservationsRef.current.delete(cameraId);
                            }

                            return currentCameraIds;
                        }
                        return prevIds;
                    });

                    // Composite frames with overlays and send to canvas workers
                    const compositor = frameCompositorRef.current!;
                    for (const frameData of frames) {
                        const observation = latestObservationsRef.current.get(frameData.cameraId) || null;

                        // Composite the frame with overlay
                        const compositeBitmap = await compositor.compositeFrame(
                            frameData.bitmap,
                            observation
                        );
                        if (frameSubscribersRef.current.size > 0) {
                            const clonedBitmap = await createImageBitmap(compositeBitmap);
                            frameSubscribersRef.current.forEach(callback => {
                                callback(frameData.cameraId, clonedBitmap);
                            });
                        }
                        // Send composited frame to worker
                        canvasManagerRef.current!.sendFrameToWorker(
                            frameData.cameraId,
                            compositeBitmap
                        );
                    }

                    // Acknowledge the highest frame number
                    if (frameNumbers.size > 0) {
                        const maxFrameNumber = Math.max(...Array.from(frameNumbers));
                        ws.send({type: 'frameAcknowledgment', frameNumber: maxFrameNumber});
                    }
                } catch (error) {
                    console.error('Error processing frame:', error);
                    throw error;
                }
            }
            // Handle text/JSON messages (logs, framerate updates, charuco observations, etc.)
            else if (typeof event.data === 'string') {
                try {
                    const jsonData = JSON.parse(event.data);

                    // Handle CharucoOverlayDataMessage (dictionary of camera_id -> observation)
                    if (isCharucoOverlayDataMessage(jsonData)) {
                        // Store observations for each camera
                        for (const [cameraId, observation] of Object.entries(jsonData)) {
                            latestObservationsRef.current.set(cameraId, observation);
                        }
                    }
                    // Handle log records
                    else if (isLogRecord(jsonData)) {
                        dispatch(logAdded(jsonData));
                    }
                    // Handle framerate updates
                    else if (isFramerateUpdate(jsonData)) {
                        dispatch(backendFramerateUpdated(jsonData.backend_framerate));
                        dispatch(frontendFramerateUpdated(jsonData.frontend_framerate));
                    }
                    // Handle other message types
                    else {
                        console.debug('Received unhandled JSON message:', jsonData);
                    }
                } catch (error) {
                    console.error('Error parsing JSON message:', error);
                    throw error;
                }
            }
        };

        ws.on('state-change', handleStateChange);
        ws.on('message', handleMessage);

        // Auto-connect
        ws.connect();

        return () => {
            ws.off('state-change', handleStateChange);
            ws.off('message', handleMessage);
            ws.disconnect();
        };
    }, [dispatch]);

    const connect = useCallback((): void => {
        wsConnectionRef.current?.connect();
    }, []);

    const disconnect = useCallback((): void => {
        wsConnectionRef.current?.disconnect();
    }, []);

    const send = useCallback((data: string | object): void => {
        wsConnectionRef.current?.send(data);
    }, []);

    const setCanvasForCamera = useCallback((cameraId: string, canvas: HTMLCanvasElement): void => {
        canvasManagerRef.current?.setCanvasForCamera(cameraId, canvas);
    }, []);

    const getFps = useCallback((cameraId: string): number | null => {
        return frameProcessorRef.current?.getFps(cameraId) ?? null;
    }, []);
    const subscribeToFrames = useCallback((callback: FrameSubscriber): (() => void) => {
        frameSubscribersRef.current.add(callback);
        return () => {
            frameSubscribersRef.current.delete(callback);
        };
    }, []);
    return (
        <ServerContext.Provider value={{
            isConnected,
            connect,
            disconnect,
            send,
            setCanvasForCamera,
            getFps,
            connectedCameraIds,
            subscribeToFrames
        }}>
            {children}
        </ServerContext.Provider>
    );
};

export const useServer = (): ServerContextValue => {
    const context = useContext(ServerContext);
    if (!context) {
        throw new Error('useServer must be used within ServerContextProvider');
    }
    return context;
};
