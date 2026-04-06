// ServerContextProvider.tsx
import React, { createContext, ReactNode, useContext, useEffect, useRef, useState, useCallback, useMemo } from 'react';

import { ConnectionState, WebSocketConnection } from "@/services/server/server-helpers/websocket-connection";
import { FrameProcessor } from "@/services/server/server-helpers/frame-processor/frame-processor";
import { CanvasManager } from "@/services/server/server-helpers/canvas-manager";
import { serverUrls } from "@/services";
import {DetailedFramerate, FramerateStore} from "@/services/server/server-helpers/framerate-store";
import {LogStore, LogRecord} from "@/services/server/server-helpers/log-store";
import { Point3d, RigidBodyPose } from "@/components/viewport3d/viewport3d-types";

interface ServerContextValue {
    isConnected: boolean;
    connect: () => void;
    disconnect: () => void;
    send: (data: string | object) => void;
    setCanvasForCamera: (cameraId: string, canvas: HTMLCanvasElement) => void;
    getFps: (cameraId: string) => number | null;
    getServerFps: () => number | null;
    getFramerateStore: () => FramerateStore;
    getLogStore: () => LogStore;
    connectedCameraIds: string[];
    updateServerConnection: (host: string, port: number) => void;
    subscribeToTrackedPoints: (cb: (points: Map<string, Point3d>) => void) => () => void;
    subscribeToRigidBodies: (cb: (poses: Map<string, RigidBodyPose>) => void) => () => void;
    getLatestTrackedPoints: () => Map<string, Point3d>;
}

const ServerContext = createContext<ServerContextValue | null>(null);

// Compare two already-sorted string arrays without allocating
function sortedArraysEqual(a: string[], b: string[]): boolean {
    if (a.length !== b.length) return false;
    for (let i = 0; i < a.length; i++) {
        if (a[i] !== b[i]) return false;
    }
    return true;
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
    // Reactive state - only updates when camera list actually changes
    const [isConnected, setIsConnected] = useState<boolean>(false);
    const [connectedCameraIds, setConnectedCameraIds] = useState<string[]>([]);

    // Service instances
    const wsConnectionRef = useRef<WebSocketConnection | null>(null);
    const frameProcessorRef = useRef<FrameProcessor | null>(null);
    const canvasManagerRef = useRef<CanvasManager | null>(null);
    const framerateStoreRef = useRef<FramerateStore>(new FramerateStore());
    const logStoreRef = useRef<LogStore>(new LogStore());

    // Latest server-side (backend) FPS stored in a ref for non-reactive access
    const serverFpsRef = useRef<number | null>(null);

    // 3D data refs and subscriber sets
    const trackedPointsRef = useRef<Map<string, Point3d>>(new Map());
    const rigidBodiesRef = useRef<Map<string, RigidBodyPose>>(new Map());
    const trackedPointsSubscribersRef = useRef<Set<(points: Map<string, Point3d>) => void>>(new Set());
    const rigidBodiesSubscribersRef = useRef<Set<(poses: Map<string, RigidBodyPose>) => void>>(new Set());

    // Holds the latest binary payload received from the WebSocket.
    // The WebSocket onmessage handler writes here synchronously;
    // a separate rAF-driven processing loop reads and clears it.
    // This decouples decoding from the WebSocket message storm,
    // preventing promise starvation where createImageBitmap microtasks
    // can never resolve because the browser dispatches onmessage events
    // back-to-back in a single macrotask without yielding.
    const pendingPayloadRef = useRef<ArrayBuffer | null>(null);
    const processingFrameRef = useRef<boolean>(false);
    const frameLoopRef = useRef<number | null>(null);

    // Cached sorted camera IDs from the last frame — compared by value to avoid
    // per-frame Array.from().sort() allocations when the camera list hasn't changed.
    const lastCameraIdsRef = useRef<string[]>([]);

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
                serverFpsRef.current = null;
                processingFrameRef.current = false;
                pendingPayloadRef.current = null;
                lastCameraIdsRef.current = [];
                framerateStoreRef.current.clear();
                trackedPointsRef.current = new Map();
                rigidBodiesRef.current = new Map();
                setConnectedCameraIds([]);
            }
        };

        // Process a decoded frame result: update camera list, dispatch to workers, send ack.
        const dispatchFrames = (
            result: Awaited<ReturnType<FrameProcessor['processFramePayload']>>
        ): void => {
            if (!result) return;

            const { frames, cameraIds, frameNumbers } = result;

            // Only allocate a new sorted array if the camera set actually changed.
            // Compare against the cached ref to avoid Array.from().sort() on every frame.
            const lastIds = lastCameraIdsRef.current;
            let cameraListChanged = lastIds.length !== cameraIds.size;
            if (!cameraListChanged) {
                for (const id of lastIds) {
                    if (!cameraIds.has(id)) {
                        cameraListChanged = true;
                        break;
                    }
                }
            }

            if (cameraListChanged) {
                const newIds = Array.from(cameraIds).sort();
                lastCameraIdsRef.current = newIds;

                setConnectedCameraIds(prevIds => {
                    if (!sortedArraysEqual(prevIds, newIds)) {
                        const removedCameras = prevIds.filter(id => !cameraIds.has(id));
                        for (const cameraId of removedCameras) {
                            canvasManagerRef.current?.terminateWorker(cameraId);
                        }
                        return newIds;
                    }
                    return prevIds;
                });
            }

            for (const frameData of frames) {
                canvasManagerRef.current!.sendFrameToWorker(
                    frameData.cameraId,
                    frameData.bitmap
                );
            }

            if (frameNumbers.size > 0) {
                const maxFrameNumber = Math.max(...Array.from(frameNumbers));
                ws.send({ type: 'frameAcknowledgment', frameNumber: maxFrameNumber });
            }
        };

        // rAF-driven processing loop. Runs on its own macrotask boundary,
        // so createImageBitmap promises can resolve without being starved
        // by the WebSocket onmessage dispatch loop.
        const processFrameLoop = async (): Promise<void> => {
            if (!processingFrameRef.current && pendingPayloadRef.current !== null) {
                const payload = pendingPayloadRef.current;
                pendingPayloadRef.current = null;
                processingFrameRef.current = true;
                try {
                    const result = await frameProcessorRef.current!.processFramePayload(payload);
                    dispatchFrames(result);
                } catch (error) {
                    console.error('Error processing frame:', error);
                } finally {
                    processingFrameRef.current = false;
                }
            }
            frameLoopRef.current = requestAnimationFrame(processFrameLoop);
        };

        frameLoopRef.current = requestAnimationFrame(processFrameLoop);

        const handleMessage = (event: MessageEvent): void => {
            // Handle binary frame data: just buffer the latest payload.
            // Older unprocessed payloads are overwritten (frame dropping).
            if (event.data instanceof ArrayBuffer) {
                pendingPayloadRef.current = event.data;
            }
            // Handle text/JSON messages (logs, framerate updates, etc.)
            else if (typeof event.data === 'string') {
                // Skip heartbeat pong responses — they're plain text, not JSON
                if (event.data === 'pong') return;

                try {
                    const jsonData = JSON.parse(event.data);

                    // Handle log records
                    if (isLogRecord(jsonData)) {
                        logStoreRef.current.add(jsonData);
                    }
                    // Handle framerate updates
                    else if (isFramerateUpdate(jsonData)) {
                        // Store backend FPS in ref for fast non-reactive access
                        serverFpsRef.current = jsonData.backend_framerate.mean_frames_per_second;
                        // Update mutable framerate store (no Redux, no re-renders)
                        framerateStoreRef.current.updateBackend(jsonData.backend_framerate);
                        framerateStoreRef.current.updateFrontend(jsonData.frontend_framerate);
                    }
                    // Handle tracked 3D points
                    else if (jsonData.tracked_points3d && typeof jsonData.tracked_points3d === 'object') {
                        const pointsMap = new Map<string, Point3d>();
                        for (const [name, pt] of Object.entries(jsonData.tracked_points3d)) {
                            const p = pt as { x: number; y: number; z: number };
                            pointsMap.set(name, { x: p.x, y: p.y, z: p.z });
                        }
                        trackedPointsRef.current = pointsMap;
                        for (const cb of trackedPointsSubscribersRef.current) {
                            cb(pointsMap);
                        }
                    }
                    // Handle rigid body poses
                    else if (jsonData.rigid_body_poses && typeof jsonData.rigid_body_poses === 'object') {
                        const posesMap = new Map<string, RigidBodyPose>();
                        for (const [key, pose] of Object.entries(jsonData.rigid_body_poses)) {
                            posesMap.set(key, pose as RigidBodyPose);
                        }
                        rigidBodiesRef.current = posesMap;
                        for (const cb of rigidBodiesSubscribersRef.current) {
                            cb(posesMap);
                        }
                    }
                    // Handle other message types (silently ignored to avoid
                    // retaining object references in the DevTools console)
                } catch (error) {
                    console.error('Error parsing JSON message:', error);
                }
            }
        };

        ws.on('state-change', handleStateChange);
        ws.on('message', handleMessage);

        // Connection is driven by ServerConnectionStatus via the connect() callback.
        // No auto-connect here — the component's autoConnectWs loop handles it.

        return () => {
            ws.off('state-change', handleStateChange);
            ws.off('message', handleMessage);
            ws.disconnect();
            if (frameLoopRef.current !== null) {
                cancelAnimationFrame(frameLoopRef.current);
                frameLoopRef.current = null;
            }
        };
    }, []);

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

    const getServerFps = useCallback((): number | null => {
        return serverFpsRef.current;
    }, []);

    const getFramerateStore = useCallback((): FramerateStore => {
        return framerateStoreRef.current;
    }, []);

    const getLogStore = useCallback((): LogStore => {
        return logStoreRef.current;
    }, []);

    const subscribeToTrackedPoints = useCallback((cb: (points: Map<string, Point3d>) => void): () => void => {
        trackedPointsSubscribersRef.current.add(cb);
        return () => { trackedPointsSubscribersRef.current.delete(cb); };
    }, []);

    const subscribeToRigidBodies = useCallback((cb: (poses: Map<string, RigidBodyPose>) => void): () => void => {
        rigidBodiesSubscribersRef.current.add(cb);
        return () => { rigidBodiesSubscribersRef.current.delete(cb); };
    }, []);

    const getLatestTrackedPoints = useCallback((): Map<string, Point3d> => {
        return trackedPointsRef.current;
    }, []);

    const updateServerConnection = useCallback((host: string, port: number): void => {
        // Update the singleton so HTTP endpoints also update
        serverUrls.setHost(host);
        serverUrls.setPort(port);

        // Update the WebSocket URL and reconnect
        const ws = wsConnectionRef.current;
        if (ws) {
            ws.disconnect();
            ws.updateUrl(serverUrls.getWebSocketUrl());
            // The auto-reconnect loop in ServerConnectionStatus will re-trigger connect()
        }
    }, []);

    const contextValue = useMemo(() => ({
        isConnected,
        connect,
        disconnect,
        send,
        setCanvasForCamera,
        getFps,
        getServerFps,
        getFramerateStore,
        getLogStore,
        connectedCameraIds,
        updateServerConnection,
        subscribeToTrackedPoints,
        subscribeToRigidBodies,
        getLatestTrackedPoints,
    }), [isConnected, connectedCameraIds, connect, disconnect, send, setCanvasForCamera, getFps, getServerFps, getFramerateStore, getLogStore, updateServerConnection, subscribeToTrackedPoints, subscribeToRigidBodies, getLatestTrackedPoints]);

    return (
        <ServerContext.Provider value={contextValue}>
            {children}
        </ServerContext.Provider>
    );
};

export const useServer = (): ServerContextValue => {
    const context = useContext(ServerContext);
    if (!context) throw new Error('useServer must be used within ServerContextProvider');
    return context;
};
