// ServerContextProvider.tsx
import React, { createContext, ReactNode, useContext, useEffect, useRef, useState, useCallback } from 'react';
import { useDispatch } from 'react-redux';
import { AppDispatch } from '@/store/types';

import { ConnectionState, WebSocketConnection } from "@/services/server/server-helpers/websocket-connection";
import { FrameProcessor } from "@/services/server/server-helpers/frame-processor/frame-processor";
import { CanvasManager } from "@/services/server/server-helpers/canvas-manager";
import { serverUrls } from "@/services";
import {
    logAdded,
    LogRecord,
    backendFramerateUpdated,
    frontendFramerateUpdated,
    DetailedFramerate
} from '@/store';

interface ServerContextValue {
    isConnected: boolean;
    connect: () => void;
    disconnect: () => void;
    send: (data: string | object) => void;
    setCanvasForCamera: (cameraId: string, canvas: HTMLCanvasElement) => void;
    getFps: (cameraId: string) => number | null;
    connectedCameraIds: string[];
}

const ServerContext = createContext<ServerContextValue | null>(null);

// Helper to compare arrays efficiently
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

export const ServerContextProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    const dispatch = useDispatch<AppDispatch>();

    // Reactive state - only updates when camera list actually changes
    const [isConnected, setIsConnected] = useState<boolean>(false);
    const [connectedCameraIds, setConnectedCameraIds] = useState<string[]>([]);

    // Service instances
    const wsConnectionRef = useRef<WebSocketConnection | null>(null);
    const frameProcessorRef = useRef<FrameProcessor | null>(null);
    const canvasManagerRef = useRef<CanvasManager | null>(null);

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
                setConnectedCameraIds([]);
            }
        };

        const handleMessage = async (event: MessageEvent): Promise<void> => {
            // Handle binary frame data
            if (event.data instanceof ArrayBuffer) {
                try {
                    const result = await frameProcessorRef.current!.processFramePayload(event.data);
                    if (!result) return;

                    const { frames, cameraIds, frameNumbers } = result;

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
                            }

                            return currentCameraIds;
                        }
                        return prevIds; // Return same reference to prevent re-render
                    });

                    // Send frames to canvas workers
                    for (const frameData of frames) {
                        canvasManagerRef.current!.sendFrameToWorker(
                            frameData.cameraId,
                            frameData.bitmap
                        );
                    }

                    // Acknowledge the highest frame number
                    if (frameNumbers.size > 0) {
                        const maxFrameNumber = Math.max(...Array.from(frameNumbers));
                        ws.send({ type: 'frameAcknowledgment', frameNumber: maxFrameNumber });
                    }
                } catch (error) {
                    console.error('Error processing frame:', error);
                }
            }
            // Handle text/JSON messages (logs, framerate updates, etc.)
            else if (typeof event.data === 'string') {
                try {
                    const jsonData = JSON.parse(event.data);

                    // Handle log records
                    if (isLogRecord(jsonData)) {
                        dispatch(logAdded(jsonData));
                    }
                    // Handle framerate updates
                    else if (isFramerateUpdate(jsonData)) {
                        // Dispatch full detailed framerate data to Redux store
                        dispatch(backendFramerateUpdated(jsonData.backend_framerate));
                        dispatch(frontendFramerateUpdated(jsonData.frontend_framerate));
                    }
                    // Handle other message types
                    else {
                        console.debug('Received unhandled JSON message:', jsonData);
                    }
                } catch (error) {
                    console.error('Error parsing JSON message:', error);
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

    return (
        <ServerContext.Provider value={{
            isConnected,
            connect,
            disconnect,
            send,
            setCanvasForCamera,
            getFps,
            connectedCameraIds
        }}>
            {children}
        </ServerContext.Provider>
    );
};

export const useServer = (): ServerContextValue => {
    const context = useContext(ServerContext);
    if (!context) throw new Error('useServer must be used within ServerContextProvider');
    return context;
};
