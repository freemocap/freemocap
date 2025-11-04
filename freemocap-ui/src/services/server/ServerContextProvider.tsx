import React, {createContext, ReactNode, useCallback, useEffect, useRef, useState} from 'react';
import {useDispatch} from 'react-redux';
import {AppDispatch} from '@/store/types';

import {ConnectionState, WebSocketConnection} from "@/services/server/server-helpers/websocket-connection";
import {FrameProcessor} from "@/services/server/server-helpers/frame-processor/frame-processor";
import {CanvasManager} from "@/services/server/server-helpers/canvas-manager";
import {backendFramerateUpdated, DetailedFramerate, frontendFramerateUpdated, logAdded, LogRecord} from '@/store';
import {
    CharucoObservation,
    CharucoOverlayDataMessage,
    CharucoOverlayDataMessageSchema
} from "@/services/server/server-helpers/charuco_types";
import {FrameCompositor} from "@/services/server/server-helpers/frame_compositor";
import {serverUrls} from "@/hooks/server-urls";

type FrameSubscriber = (bitmap: ImageBitmap) => void;

export interface ServerContextValue {
    isConnected: boolean;
    connect: () => void;
    disconnect: () => void;
    send: (data: string | object) => void;
    setCanvasForCamera: (cameraId: string, canvas: HTMLCanvasElement) => void;
    getFps: (cameraId: string) => number | null;
    connectedCameraIds: string[];
    subscribeToFrames: (cameraId:string,callback: FrameSubscriber) => () => void;
}

export const ServerContext = createContext<ServerContextValue | null>(null);

function arraysEqual(a: string[], b: string[]): boolean {
    if (a.length !== b.length) return false;
    const sortedA = [...a].sort();
    const sortedB = [...b].sort();
    return sortedA.every((val, idx) => val === sortedB[idx]);
}

function isLogRecord(data: any): data is LogRecord {
    return (
        data &&
        typeof data === 'object' &&
        data.message_type === 'log_record' &&
        typeof data.levelname === 'string' &&
        typeof data.message === 'string'
    );
}

interface FramerateUpdateMessage {
    message_type: 'framerate_update';
    camera_group_id: string;
    backend_framerate: DetailedFramerate;
    frontend_framerate: DetailedFramerate;
}

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

function isCharucoOverlayDataMessage(data: any): data is CharucoOverlayDataMessage {
    const result = CharucoOverlayDataMessageSchema.safeParse(data);
    return result.success;
}

export const ServerContextProvider: React.FC<{ children: ReactNode }> = ({children}) => {
    const dispatch = useDispatch<AppDispatch>();

    const [isConnected, setIsConnected] = useState<boolean>(false);
    const [connectedCameraIds, setConnectedCameraIds] = useState<string[]>([]);

    const wsConnectionRef = useRef<WebSocketConnection | null>(null);
    const frameProcessorRef = useRef<FrameProcessor | null>(null);
    const canvasManagerRef = useRef<CanvasManager | null>(null);
    const frameCompositorRef = useRef<FrameCompositor | null>(null);
    const frameSubscribersRef = useRef<Map<string, Set<FrameSubscriber>>>(new Map());
    const latestObservationsRef = useRef<Map<string, CharucoObservation>>(new Map());

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
            if (event.data instanceof ArrayBuffer) {
                try {
                    const result = await frameProcessorRef.current!.processFramePayload(event.data);
                    if (!result) return;

                    const {frames, cameraIds, frameNumbers} = result;

                    const currentCameraIds = Array.from(cameraIds).sort();
                    setConnectedCameraIds(prevIds => {
                        if (!arraysEqual(prevIds, currentCameraIds)) {
                            console.log(`Camera list updated: ${currentCameraIds.join(', ')}`);

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

                    // Track remaining frames to render (simple counter - most efficient)
                    let remainingFrames = frames.length;
                    const maxFrameNumber = Math.max(...Array.from(frameNumbers));

                    const onFrameRendered = (): void => {
                        remainingFrames--;
                        if (remainingFrames === 0) {
                            // ALL frames rendered - now we can ACK
                            ws.send({type: 'frameAcknowledgment', frameNumber: maxFrameNumber});
                        }
                    };

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
                            const subscribers = frameSubscribersRef.current.get(frameData.cameraId);
                            if (subscribers && subscribers.size > 0) {
                                // Create one clone per subscriber for THIS camera only
                                for (const callback of subscribers) {
                                    const clonedBitmap = await createImageBitmap(compositeBitmap);
                                    callback(clonedBitmap);
                                }
                            }
                        }

                        // Send composited frame to worker - ACK only when rendered
                        canvasManagerRef.current!.sendFrameToWorker(
                            frameData.cameraId,
                            compositeBitmap,
                            onFrameRendered
                        );
                    }

                    // Note: ACK is sent by onFrameRendered callback after ALL frames are done
                } catch (error) {
                    console.error('Error processing frame:', error);
                    throw error;
                }
            }
            else if (typeof event.data === 'string') {
                try {
                    const jsonData = JSON.parse(event.data);

                    if (isCharucoOverlayDataMessage(jsonData)) {
                        for (const [cameraId, observation] of Object.entries(jsonData)) {
                            latestObservationsRef.current.set(cameraId, observation);
                        }
                    }
                    else if (isLogRecord(jsonData)) {
                        dispatch(logAdded(jsonData));
                    }
                    else if (isFramerateUpdate(jsonData)) {
                        dispatch(backendFramerateUpdated(jsonData.backend_framerate));
                        dispatch(frontendFramerateUpdated(jsonData.frontend_framerate));
                    }
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

    const subscribeToFrames = useCallback((cameraId: string, callback: FrameSubscriber): (() => void) => {
        if (!frameSubscribersRef.current.has(cameraId)) {
            frameSubscribersRef.current.set(cameraId, new Set());
        }
        frameSubscribersRef.current.get(cameraId)!.add(callback);

        return () => {
            const subscribers = frameSubscribersRef.current.get(cameraId);
            subscribers?.delete(callback);
            if (subscribers?.size === 0) {
                frameSubscribersRef.current.delete(cameraId);
            }
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

