import React, {createContext, ReactNode, useCallback, useEffect, useRef, useState} from 'react';
import {useDispatch} from 'react-redux';
import {AppDispatch} from '@/store/types';

import {ConnectionState, WebSocketConnection} from "@/services/server/server-helpers/websocket-connection";
import {FrameProcessor} from "@/services/server/server-helpers/frame-processor/frame-processor";
import {CanvasManager} from "@/services/server/server-helpers/canvas-manager";
import {backendFramerateUpdated, DetailedFramerate, frontendFramerateUpdated, logAdded, LogRecord} from '@/store';

import {FrameCompositor} from "@/services/server/server-helpers/frame_compositor";
import {serverUrls} from "@/hooks/server-urls";
import {
    CharucoObservation,
    CharucoOverlayDataMessage,
    CharucoOverlayDataMessageSchema
} from "@/services/server/server-helpers/image-overlay/charuco-types";
import {
    MediapipeOverlayDataMessage,
    MediapipeOverlayDataMessageSchema
} from "@/services/server/server-helpers/image-overlay/mediapipe-types";
import {
    OverlayManager,
    OverlayRendererFactory
} from "@/services/server/server-helpers/image-overlay/overlay-renderer-factory";
import {ModelInfo} from "@/services/server/server-helpers/image-overlay/image-overlay-system";
import {MediapipeObservation} from "@/services/server/server-helpers/image-overlay/mediapipe-overlay-renderer";

type FrameSubscriber = (bitmap: ImageBitmap) => void;
type TrackedPointsSubscriber = (points: Map<string, Point3d>) => void;

export interface Point3d {
    x: number;
    y: number;
    z: number;
}

export interface ServerContextValue {
    isConnected: boolean;
    connect: () => void;
    disconnect: () => void;
    send: (data: string | object) => void;
    setCanvasForCamera: (cameraId: string, canvas: HTMLCanvasElement) => void;
    getFps: (cameraId: string) => number | null;
    connectedCameraIds: string[];
    subscribeToFrames: (cameraId: string, callback: FrameSubscriber) => () => void;
    subscribeToTrackedPoints: (callback: TrackedPointsSubscriber) => () => void;
    getLatestTrackedPoints: () => Map<string, Point3d>;
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
function isMediapipeOverlayDataMessage(data: any): data is MediapipeOverlayDataMessage {
    const result = MediapipeOverlayDataMessageSchema.safeParse(data);
    return result.success;
}

function handleModelInfoUpdate(modelInfo: ModelInfo): void {
    console.log(`Received model info for tracker: ${modelInfo.tracker_name}`);
    OverlayRendererFactory.setModelInfo(modelInfo.tracker_name, modelInfo);
}

export const ServerContextProvider: React.FC<{ children: ReactNode }> = ({children}) => {
    const dispatch = useDispatch<AppDispatch>();

    const [isConnected, setIsConnected] = useState<boolean>(false);
    const [connectedCameraIds, setConnectedCameraIds] = useState<string[]>([]);

    const wsConnectionRef = useRef<WebSocketConnection | null>(null);
    const frameProcessorRef = useRef<FrameProcessor | null>(null);
    const canvasManagerRef = useRef<CanvasManager | null>(null);
    const overlayManagerRef = useRef<OverlayManager | null>(null);
    const frameCompositorRef = useRef<FrameCompositor | null>(null);
    const frameSubscribersRef = useRef<Map<string, Set<FrameSubscriber>>>(new Map());
    const latestObservationsRef = useRef<Map<string, CharucoObservation|MediapipeObservation>>(new Map());
    const latestTrackedPoints = useRef<Map<string, Point3d>>(new Map());
    const trackedPointsSubscribersRef = useRef<Set<TrackedPointsSubscriber>>(new Set());

    useEffect(() => {
        wsConnectionRef.current = new WebSocketConnection({
            url: serverUrls.getWebSocketUrl(),
            reconnectDelay: 1000,
            maxReconnectAttempts: 5,
            heartbeatInterval: 30000
        });
        frameProcessorRef.current = new FrameProcessor();
        canvasManagerRef.current = new CanvasManager();
        overlayManagerRef.current = new OverlayManager();
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
            latestTrackedPoints.current.clear();
            trackedPointsSubscribersRef.current.clear();
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
                overlayManagerRef.current?.clearAll();
                latestObservationsRef.current.clear();
                latestTrackedPoints.current.clear();
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
                                overlayManagerRef.current?.clearCamera(cameraId);  // Clear overlay renderer
                                latestObservationsRef.current.delete(cameraId);
                            }

                            return currentCameraIds;
                        }
                        return prevIds;
                    });

                    // Track remaining frames to render
                    let remainingFrames = frames.length;
                    const maxFrameNumber = Math.max(...Array.from(frameNumbers));

                    const onFrameRendered = (): void => {
                        remainingFrames--;
                        if (remainingFrames === 0) {
                            ws.send({type: 'frameAcknowledgment', frameNumber: maxFrameNumber});
                        }
                    };

                    // Process frames with generic overlay manager
                    const overlayManager = overlayManagerRef.current!;
                    for (const frameData of frames) {
                        const observation = latestObservationsRef.current.get(frameData.cameraId) || null;

                        // Use generic overlay manager to composite frame
                        const compositeBitmap = await overlayManager.processFrame(
                            frameData.cameraId,
                            frameData.bitmap,
                            observation
                        );

                        // Send to subscribers if any
                        if (frameSubscribersRef.current.size > 0) {
                            const subscribers = frameSubscribersRef.current.get(frameData.cameraId);
                            if (subscribers && subscribers.size > 0) {
                                for (const callback of subscribers) {
                                    const clonedBitmap = await createImageBitmap(compositeBitmap);
                                    callback(clonedBitmap);
                                }
                            }
                        }

                        // Send to canvas worker
                        canvasManagerRef.current!.sendFrameToWorker(
                            frameData.cameraId,
                            compositeBitmap,
                            onFrameRendered
                        );
                    }
                } catch (error) {
                    console.error('Error processing frame:', error);
                    throw error;
                }
            }
            else if (typeof event.data === 'string') {
                try {
                    const jsonData = JSON.parse(event.data);

                    // Handle different observation types
                    if (isCharucoOverlayDataMessage(jsonData)) {
                        for (const [cameraId, observation] of Object.entries(jsonData)) {
                            latestObservationsRef.current.set(cameraId, observation);
                        }
                    }
                    else if (isMediapipeOverlayDataMessage(jsonData)) {
                        for (const [cameraId, observation] of Object.entries(jsonData)) {
                            latestObservationsRef.current.set(cameraId, observation);
                        }
                    }
                    else if ('model_info' in jsonData && jsonData.model_info) {
                        // Handle model info updates
                        handleModelInfoUpdate(jsonData.model_info);
                    }
                    else if ('tracked_points3d' in jsonData) {
                        // Handle 3D tracked points
                        console.log(`Received 3d data - ${JSON.stringify(jsonData.tracked_points3d)}`);
                        latestTrackedPoints.current = new Map(Object.entries(jsonData.tracked_points3d));

                        for (const subscriber of trackedPointsSubscribersRef.current) {
                            subscriber(latestTrackedPoints.current);
                        }
                    }
                    else if (isLogRecord(jsonData)) {
                        dispatch(logAdded(jsonData));
                    }
                    else if (isFramerateUpdate(jsonData)) {
                        dispatch(backendFramerateUpdated(jsonData.backend_framerate));
                        dispatch(frontendFramerateUpdated(jsonData.frontend_framerate));
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

    const subscribeToTrackedPoints = useCallback((callback: TrackedPointsSubscriber): (() => void) => {
        trackedPointsSubscribersRef.current.add(callback);

        // Immediately call with current points if any exist
        if (latestTrackedPoints.current.size > 0) {
            callback(latestTrackedPoints.current);
        }

        return () => {
            trackedPointsSubscribersRef.current.delete(callback);
        };
    }, []);

    const getLatestTrackedPoints = useCallback((): Map<string, Point3d> => {
        return latestTrackedPoints.current;
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
            subscribeToFrames,
            subscribeToTrackedPoints,
            getLatestTrackedPoints
        }}>
            {children}
        </ServerContext.Provider>
    );
};
