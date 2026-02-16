import React, {createContext, ReactNode, useCallback, useEffect, useRef, useState} from 'react';
import {useDispatch} from 'react-redux';
import {AppDispatch} from '@/store/types';

import {ConnectionState, WebSocketConnection} from "@/services/server/server-helpers/websocket-connection";
import {FrameProcessor} from "@/services/server/server-helpers/frame-processor/frame-processor";
import {CanvasManager} from "@/services/server/server-helpers/canvas-manager";
import {
    backendFramerateUpdated,
    frontendFramerateUpdated,
    logAdded,
    serverSettingsCleared,
    serverSettingsUpdated,
} from '@/store';

import {serverUrls} from "@/hooks/server-urls";
import {CharucoObservation} from "@/services/server/server-helpers/image-overlay/charuco-types";
import {OverlayManager} from "@/services/server/server-helpers/image-overlay/overlay-renderer-factory";
import {MediapipeObservation} from "@/services/server/server-helpers/image-overlay/mediapipe-overlay-renderer";
import {
    arraysEqual, handleModelInfoUpdate,
    isCharucoOverlayDataMessage, isFramerateUpdate, isLogRecord, isMediapipeOverlayDataMessage,
    isSettingsStateMessage
} from "@/services/server/server-helpers/websocket-message-types";
import {RigidBodyPose} from "@/components/viewport3d/viewport3d-types";

type FrameSubscriber = (bitmap: ImageBitmap) => void;
type TrackedPointsSubscriber = (points: Map<string, Point3d>) => void;
type RigidBodiesSubscriber = (poses: Map<string, RigidBodyPose>) => void;

export interface Point3d {
    x: number;
    y: number;
    z: number;
}

export interface ServerContextValue {
    isConnected: boolean;
    connectionState: ConnectionState;
    connect: () => void;
    disconnect: () => void;
    send: (data: string | object) => void;
    setCanvasForCamera: (cameraId: string, canvas: HTMLCanvasElement) => void;
    getFps: (cameraId: string) => number | null;
    connectedCameraIds: string[];
    subscribeToFrames: (cameraId: string, callback: FrameSubscriber) => () => void;
    subscribeToTrackedPoints: (callback: TrackedPointsSubscriber) => () => void;
    getLatestTrackedPoints: () => Map<string, Point3d>;
    subscribeToRigidBodies: (callback: RigidBodiesSubscriber) => () => void;
}

export const ServerContext = createContext<ServerContextValue | null>(null);

export const ServerContextProvider: React.FC<{ children: ReactNode }> = ({children}) => {
    const dispatch = useDispatch<AppDispatch>();

    const [isConnected, setIsConnected] = useState<boolean>(false);
    const [connectionState, setConnectionState] = useState<ConnectionState>(ConnectionState.DISCONNECTED);
    const [connectedCameraIds, setConnectedCameraIds] = useState<string[]>([]);
    // Tracks the port so the WebSocket connection is recreated when it changes.
    // Updated via serverUrls.onPortChange() subscription.
    const [serverPort, setServerPort] = useState<number>(serverUrls.getPort());

    const wsConnectionRef = useRef<WebSocketConnection | null>(null);
    const frameProcessorRef = useRef<FrameProcessor | null>(null);
    const canvasManagerRef = useRef<CanvasManager | null>(null);
    const overlayManagerRef = useRef<OverlayManager | null>(null);
    const frameSubscribersRef = useRef<Map<string, Set<FrameSubscriber>>>(new Map());
    const latestCharucoRef = useRef<Map<string, CharucoObservation>>(new Map());
    const latestMediapipeRef = useRef<Map<string, MediapipeObservation>>(new Map());
    const latestTrackedPoints = useRef<Map<string, Point3d>>(new Map());
    const trackedPointsSubscribersRef = useRef<Set<TrackedPointsSubscriber>>(new Set());
    const latestRigidBodies = useRef<Map<string, RigidBodyPose>>(new Map());
    const rigidBodiesSubscribersRef = useRef<Set<RigidBodiesSubscriber>>(new Set());

    // Subscribe to port changes from the serverUrls singleton.
    // When useElectronAPI().pythonServer.start() resolves, it calls serverUrls.setPort(),
    // which triggers this callback and causes the WebSocket to reconnect on the correct port.
    useEffect(() => {
        return serverUrls.onPortChange((port: number) => {
            console.log(`[ServerContext] Port changed to ${port}, will recreate WebSocket connection`);
            setServerPort(port);
        });
    }, []);

    // Create / recreate the WebSocket connection whenever the port changes.
    useEffect(() => {
        if (wsConnectionRef.current) {
            wsConnectionRef.current.disconnect();
        }
        canvasManagerRef.current?.terminateAllWorkers();
        frameProcessorRef.current?.reset();

        wsConnectionRef.current = new WebSocketConnection({
            url: serverUrls.getWebSocketUrl(),
            reconnectDelay: 1000,
            maxReconnectAttempts: 5,
            heartbeatInterval: 30000,
            autoConnect: true,
            autoConnectInterval: 3000,
        });
        frameProcessorRef.current = new FrameProcessor();
        canvasManagerRef.current = new CanvasManager();
        overlayManagerRef.current = new OverlayManager();

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
            latestCharucoRef.current.clear();
            latestMediapipeRef.current.clear();
            latestTrackedPoints.current.clear();
            trackedPointsSubscribersRef.current.clear();
            latestRigidBodies.current.clear();
            rigidBodiesSubscribersRef.current.clear();
        };
    }, [serverPort]);

    useEffect(() => {
        const ws = wsConnectionRef.current;
        if (!ws) return;

        const handleStateChange = (newState: ConnectionState, previousState: ConnectionState): void => {
            const connected = newState === ConnectionState.CONNECTED;
            console.log(`[WS] State transition: ${previousState} → ${newState} (connected=${connected})`);
            setIsConnected(connected);
            setConnectionState(newState);

            if (previousState === ConnectionState.CONNECTED && !connected) {
                console.log('[WS] Lost connection — clearing state');
                canvasManagerRef.current?.terminateAllWorkers();
                frameProcessorRef.current?.reset();
                overlayManagerRef.current?.clearAll();
                latestCharucoRef.current.clear();
                latestMediapipeRef.current.clear();
                latestTrackedPoints.current.clear();
                setConnectedCameraIds([]);
                dispatch(serverSettingsCleared());
                latestRigidBodies.current.clear();
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
                                latestCharucoRef.current.delete(cameraId);
                                latestMediapipeRef.current.delete(cameraId);
                            }

                            return currentCameraIds;
                        }
                        return prevIds;
                    });

                    // Acknowledge receipt immediately so the backend can prepare
                    // the next frame without waiting for rendering to complete.
                    if (frameNumbers.size > 0) {
                        const maxFrameNumber = Math.max(...Array.from(frameNumbers));
                        ws.send({type: 'frameAcknowledgment', frameNumber: maxFrameNumber});
                    }

                    const overlayManager = overlayManagerRef.current!;
                    for (const frameData of frames) {
                        const charucoObservation = latestCharucoRef.current.get(frameData.cameraId) ?? null;
                        const mediapipeObservation = latestMediapipeRef.current.get(frameData.cameraId) ?? null;

                        let compositeBitmap: ImageBitmap;
                        if (charucoObservation || mediapipeObservation) {
                            compositeBitmap = await overlayManager.processFrame(
                                frameData.cameraId,
                                frameData.bitmap,
                                charucoObservation,
                                mediapipeObservation,
                            );
                        } else {
                            compositeBitmap = frameData.bitmap;
                        }

                        {
                            const subscribers = frameSubscribersRef.current.get(frameData.cameraId);
                            if (subscribers && subscribers.size > 0) {
                                for (const callback of subscribers) {
                                    const clonedBitmap = await createImageBitmap(compositeBitmap);
                                    callback(clonedBitmap);
                                }
                            }
                        }

                        canvasManagerRef.current!.sendFrameToWorker(
                            frameData.cameraId,
                            compositeBitmap,
                        );
                    }
                } catch (error) {
                    console.error('Error processing frame:', error);
                    throw error;
                }
            } else if (typeof event.data === 'string') {
                const text = event.data;

                if (text === 'pong') {
                    return;
                }
                if (text.startsWith('ping')) {
                    ws.send('pong');
                    return;
                }

                const jsonData = JSON.parse(text);

                if (isSettingsStateMessage(jsonData)) {
                    console.log(`[WS] Received settings/state v${jsonData.version}`, jsonData.settings);
                    dispatch(serverSettingsUpdated(jsonData));
                } else if (isCharucoOverlayDataMessage(jsonData)) {
                    for (const [cameraId, observation] of Object.entries(jsonData)) {
                        latestCharucoRef.current.set(cameraId, observation as CharucoObservation);
                    }
                } else if (isMediapipeOverlayDataMessage(jsonData)) {
                    for (const [cameraId, observation] of Object.entries(jsonData)) {
                        latestMediapipeRef.current.set(cameraId, observation as MediapipeObservation);
                    }
                } else if ('model_info' in jsonData && jsonData.model_info) {
                    handleModelInfoUpdate(jsonData.model_info);
                } else if ('tracked_points3d' in jsonData) {
                    latestTrackedPoints.current = new Map(Object.entries(jsonData.tracked_points3d));
                    for (const subscriber of trackedPointsSubscribersRef.current) {
                        subscriber(latestTrackedPoints.current);
                    }
                } else if ('rigid_body_poses' in jsonData) {
                    latestRigidBodies.current = new Map(
                        Object.entries(jsonData.rigid_body_poses as Record<string, RigidBodyPose>)
                    );
                    for (const subscriber of rigidBodiesSubscribersRef.current) {
                        subscriber(latestRigidBodies.current);
                    }
                } else if (isLogRecord(jsonData)) {
                    dispatch(logAdded(jsonData));
                } else if (isFramerateUpdate(jsonData)) {
                    dispatch(backendFramerateUpdated(jsonData.backend_framerate));
                    dispatch(frontendFramerateUpdated(jsonData.frontend_framerate));
                } else {
                    console.warn('[WS] Unhandled JSON message:', Object.keys(jsonData));
                }
            }
        };

        ws.on('state-change', handleStateChange);
        ws.on('message', handleMessage);

        // Start in auto-discovery mode — silently poll until the server appears
        ws.startDiscovery();

        return () => {
            ws.off('state-change', handleStateChange);
            ws.off('message', handleMessage);
            ws.disconnect();
        };
    }, [dispatch, serverPort]);

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

    const subscribeToRigidBodies = useCallback((callback: RigidBodiesSubscriber): (() => void) => {
        rigidBodiesSubscribersRef.current.add(callback);

        if (latestRigidBodies.current.size > 0) {
            callback(latestRigidBodies.current);
        }

        return () => {
            rigidBodiesSubscribersRef.current.delete(callback);
        };
    }, []);

    return (
        <ServerContext.Provider value={{
            isConnected,
            connectionState,
            connect,
            disconnect,
            send,
            setCanvasForCamera,
            getFps,
            connectedCameraIds,
            subscribeToFrames,
            subscribeToTrackedPoints,
            getLatestTrackedPoints,
            subscribeToRigidBodies,
        }}>
            {children}
        </ServerContext.Provider>
    );
};