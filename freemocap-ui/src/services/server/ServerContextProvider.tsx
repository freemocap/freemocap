// ServerContextProvider.tsx
import React, {createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useRef, useState} from 'react';

import {ConnectionState, WebSocketConnection} from "@/services/server/server-helpers/websocket-connection";
import {FrameProcessor} from "@/services/server/server-helpers/frame-processor/frame-processor";
import {CanvasManager} from "@/services/server/server-helpers/canvas-manager";
import {serverUrls} from "@/services";
import {FramerateStore} from "@/services/server/server-helpers/framerate-store";
import {LogStore} from "@/services/server/server-helpers/log-store";
import {OverlayManager} from "@/services/server/server-helpers/image-overlay/overlay-renderer-factory";
import {CharucoObservation} from "@/services/server/server-helpers/image-overlay/charuco-types";
import {MediapipeObservation} from "@/services/server/server-helpers/image-overlay/mediapipe-types";
import {
    isFramerateUpdate,
    isFrontendPayload,
    isLogRecord
} from "@/services/server/server-helpers/websocket-message-types";
import {Point3d, RigidBodyPose} from "@/components/viewport3d";

interface ServerContextValue {
    isConnected: boolean;
    connect: () => void;
    disconnect: () => void;
    sendWebsocketMessage: (data: string | object) => void;
    setCanvasForCamera: (cameraId: string, canvas: HTMLCanvasElement) => void;
    getFps: (cameraId: string) => number | null;
    getServerFps: () => number | null;
    getFramerateStore: () => FramerateStore;
    getLogStore: () => LogStore;
    connectedCameraIds: string[];
    updateServerConnection: (host: string, port: number) => void;
    subscribeToKeypointsRaw: (cb: (points: Record<string, Point3d>) => void) => () => void;
    subscribeToKeypointsFiltered: (cb: (points: Record<string, Point3d>) => void) => () => void;
    subscribeToRigidBodies: (cb: (poses: Map<string, RigidBodyPose>) => void) => () => void;
    getLatestKeypointsRaw: () => Record<string, Point3d>;
    setOverlayVisibility: (charuco: boolean, skeleton: boolean) => void;
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

export const ServerContextProvider: React.FC<{ children: ReactNode }> = ({children}) => {
    // Reactive state - only updates when camera list actually changes
    const [isConnected, setIsConnected] = useState<boolean>(false);
    const [connectedCameraIds, setConnectedCameraIds] = useState<string[]>([]);

    // Service instances
    const wsConnectionRef = useRef<WebSocketConnection | null>(null);
    const frameProcessorRef = useRef<FrameProcessor | null>(null);
    const canvasManagerRef = useRef<CanvasManager | null>(null);
    const framerateStoreRef = useRef<FramerateStore>(new FramerateStore());
    const logStoreRef = useRef<LogStore>(new LogStore());
    const overlayManagerRef = useRef<OverlayManager | null>(null);

    // Overlay data refs - NO REACT STATE to avoid re-renders!
    const latestCharucoRef = useRef<Map<string, CharucoObservation>>(new Map());
    const latestMediapipeRef = useRef<Map<string, MediapipeObservation>>(new Map());

    // Overlay visibility flags - toggled by UI, applied in dispatchFrames
    const charucoEnabledRef = useRef<boolean>(true);
    const skeletonEnabledRef = useRef<boolean>(true);

    // Latest server-side (backend) FPS stored in a ref for non-reactive access
    const serverFpsRef = useRef<number | null>(null);

    // 3D data refs and subscriber sets
    // Plain Record — matches JSON.parse output directly, no remapping needed.
    const trackedPointsRef = useRef<Record<string, Point3d>>({});
    const rigidBodiesRef = useRef<Map<string, RigidBodyPose>>(new Map());
    const trackedPointsSubscribersRef = useRef<Set<(points: Record<string, Point3d>) => void>>(new Set());
    const rigidBodiesSubscribersRef = useRef<Set<(poses: Map<string, RigidBodyPose>) => void>>(new Set());
    const keypointsFilteredRef = useRef<Record<string, Point3d>>({});
    const keypointsFilteredSubscribersRef = useRef<Set<(points: Record<string, Point3d>) => void>>(new Set());


    // Holds the latest binary payload received from the WebSocket.
    // The WebSocket onmessage handler writes here synchronously;
    // a separate rAF-driven processing loop reads and clears it.
    // This decouples decoding from the WebSocket message storm,
    // preventing promise starvation where createImageBitmap microtasks
    // can never resolve because the browser dispatches onmessage events
    // back-to-back in a single macrotask without yielding.
    // TODO - Check if this is nonsense
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
            overlayManagerRef.current?.clearAll();
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
                trackedPointsRef.current = {};
                rigidBodiesRef.current = new Map();
                keypointsFilteredRef.current = {};
                latestCharucoRef.current.clear();
                latestMediapipeRef.current.clear();
                overlayManagerRef.current?.clearAll();
                setConnectedCameraIds([]);
            }
        };

        // Process a decoded frame result: update camera list, dispatch to workers, send ack.
        const dispatchFrames = async (
            result: Awaited<ReturnType<FrameProcessor['processFramePayload']>>
        ): Promise<void> => {
            if (!result) return;

            const {frames, cameraIds, frameNumbers} = result;

            // Only allocate a new sorted array if the camera set actually changed.
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
                            latestCharucoRef.current.delete(cameraId);
                            latestMediapipeRef.current.delete(cameraId);
                        }
                        return newIds;
                    }
                    return prevIds;
                });
            }

            // Composite overlays onto frames before sending to canvas workers
            const overlayManager = overlayManagerRef.current!;
            for (const frameData of frames) {
                const charucoObs = charucoEnabledRef.current
                    ? latestCharucoRef.current.get(frameData.cameraId) ?? null
                    : null;
                const mediapipeObs = skeletonEnabledRef.current
                    ? latestMediapipeRef.current.get(frameData.cameraId) ?? null
                    : null;

                let compositeBitmap: ImageBitmap;
                if (charucoObs || mediapipeObs) {
                    compositeBitmap = await overlayManager.processFrame(
                        frameData.cameraId,
                        frameData.bitmap,
                        charucoObs,
                        mediapipeObs,
                    );
                } else {
                    compositeBitmap = frameData.bitmap;
                }

                canvasManagerRef.current!.sendFrameToWorker(
                    frameData.cameraId,
                    compositeBitmap,
                );
            }

            if (frameNumbers.size > 0) {
                const maxFrameNumber = Math.max(...Array.from(frameNumbers));
                ws.send({type: 'frameAcknowledgment', frameNumber: maxFrameNumber});
            }
        };

        // requestAnimationFrame(rAF)-driven processing loop. Runs on its own macrotask boundary,
        // so createImageBitmap promises can resolve without being starved
        // by the WebSocket onmessage dispatch loop.
        //TODO - check if this is nonsense
        const processFrameLoop = async (): Promise<void> => {
            if (!processingFrameRef.current && pendingPayloadRef.current !== null) {
                const payload = pendingPayloadRef.current;
                pendingPayloadRef.current = null;
                processingFrameRef.current = true;
                try {
                    const result = await frameProcessorRef.current!.processFramePayload(payload);
                    await dispatchFrames(result);
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
            // Handle text/JSON messages (logs, framerate updates, frontend payloads, etc.)
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
                    // Handle charuco overlay data
                    else if (isFrontendPayload(jsonData)) {
                        if (jsonData.charuco_overlays) {
                            for (const [cameraId, charuco] of Object.entries(jsonData.charuco_overlays)) {
                                latestCharucoRef.current.set(cameraId, charuco as CharucoObservation);
                            }
                        }
                        if (jsonData.skeleton_overlays) {
                            for (const [cameraId, skeleton] of Object.entries(jsonData.skeleton_overlays)) {
                                latestMediapipeRef.current.set(cameraId, skeleton as MediapipeObservation);
                            }
                        }

                        // Keypoints arrive as plain JSON objects — assign directly, no remapping.
                        if (jsonData.keypoints_raw) {
                            trackedPointsRef.current = jsonData.keypoints_raw as Record<string, Point3d>;
                            for (const cb of trackedPointsSubscribersRef.current) {
                                cb(trackedPointsRef.current);
                            }
                        }

                        if (jsonData.keypoints_filtered) {
                            keypointsFilteredRef.current = jsonData.keypoints_filtered as Record<string, Point3d>;
                            for (const cb of keypointsFilteredSubscribersRef.current) {
                                cb(keypointsFilteredRef.current);
                            }
                        }

                        if (jsonData.rigid_body_poses) {
                            const posesMap = new Map<string, RigidBodyPose>();
                            for (const [key, pose] of Object.entries(jsonData.rigid_body_poses)) {
                                posesMap.set(key, pose as RigidBodyPose);
                            }
                            rigidBodiesRef.current = posesMap;
                            for (const cb of rigidBodiesSubscribersRef.current) cb(posesMap);
                        }
                    }
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

    const sendWebsocketMessage = useCallback((data: string | object): void => {
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

    const subscribeToKeypointsRaw = useCallback((cb: (points: Record<string, Point3d>) => void): () => void => {
        trackedPointsSubscribersRef.current.add(cb);
        return () => { trackedPointsSubscribersRef.current.delete(cb); };
    }, []);

    const subscribeToKeypointsFiltered = useCallback((cb: (points: Record<string, Point3d>) => void): () => void => {
        keypointsFilteredSubscribersRef.current.add(cb);
        return () => { keypointsFilteredSubscribersRef.current.delete(cb); };
    }, []);

    const subscribeToRigidBodies = useCallback((cb: (poses: Map<string, RigidBodyPose>) => void): () => void => {
        rigidBodiesSubscribersRef.current.add(cb);
        return () => {
            rigidBodiesSubscribersRef.current.delete(cb);
        };
    }, []);

    const getLatestKeypointsRaw = useCallback((): Record<string, Point3d> => {
        return trackedPointsRef.current;
    }, []);

    const setOverlayVisibility = useCallback((charuco: boolean, skeleton: boolean): void => {
        charucoEnabledRef.current = charuco;
        skeletonEnabledRef.current = skeleton;
        if (!charuco) latestCharucoRef.current.clear();
        if (!skeleton) latestMediapipeRef.current.clear();
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
        sendWebsocketMessage,
        setCanvasForCamera,
        getFps,
        getServerFps,
        getFramerateStore,
        getLogStore,
        connectedCameraIds,
        updateServerConnection,
        subscribeToKeypointsRaw,
        subscribeToKeypointsFiltered,
        subscribeToRigidBodies,
        getLatestKeypointsRaw,
        setOverlayVisibility,
    }), [isConnected, connectedCameraIds, connect, disconnect, sendWebsocketMessage, setCanvasForCamera, getFps, getServerFps, getFramerateStore, getLogStore, updateServerConnection, subscribeToKeypointsRaw, subscribeToKeypointsFiltered, subscribeToRigidBodies, getLatestKeypointsRaw, setOverlayVisibility]);

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
