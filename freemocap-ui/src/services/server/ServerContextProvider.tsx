// ServerContextProvider.tsx
import React, {ReactNode, useCallback, useEffect, useMemo, useRef, useState} from 'react';
import { ServerContext, type ServerContextValue } from './server-context';
export { useServer, useServerOptional, ServerContext, type ServerContextValue } from './server-context';

import {ConnectionState, WebSocketConnection} from "@/services/server/server-helpers/websocket-connection";
import {FrameProcessor} from "@/services/server/server-helpers/frame-processor/frame-processor";
import {CanvasManager} from "@/services/server/server-helpers/canvas-manager";
import {serverUrls} from "@/services";
import {FramerateStore} from "@/services/server/server-helpers/framerate-store";
import {LogStore} from "@/services/server/server-helpers/log-store";
import {
    FrontendPayloadMessage,
    isFramerateUpdate,
    isFrontendPayload,
    isLogRecord,
    isPosthocProgress,
    isTrackerSchemas,
} from "@/services/server/server-helpers/websocket-message-types";
import {TrackedObjectDefinition} from "@/services/server/server-helpers/tracked-object-definition";
import {
    BLOCK_KIND,
    isKeypointsMessage,
    parseKeypointsMessage,
} from "@/services/server/server-helpers/frame-processor/keypoints-binary-parser";
import {Point3d, BodyKinematics} from "@/components/viewport3d";
import {
    KeypointsCallback,
    KeypointsFrame,
} from "@/components/viewport3d/KeypointsSourceContext";
import {store} from "@/store";
import {pipelineProgressUpdated, PipelinePhase, PipelineType} from "@/store/slices/pipelines";
import {serverStateReceived, wsConnectionChanged, serverDisconnected} from "@/store/slices/connection/connection-slice";
import type {AppStateMessage} from "@/store/slices/connection/connection-types";

// Type guard for the server's authoritative APP_STATE snapshot
function isAppState(data: any): data is AppStateMessage {
    return (
        data &&
        typeof data === 'object' &&
        data.message_type === 'app_state' &&
        typeof data.server_pid === 'number' &&
        data.state &&
        typeof data.state === 'object'
    );
}

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
    const [isFailed, setIsFailed] = useState<boolean>(false);
    const [connectedCameraIds, setConnectedCameraIds] = useState<string[]>([]);

    // Tracker schemas — shipped by the backend on WS connect/reconfigure.
    const trackerSchemasRef = useRef<Record<string, TrackedObjectDefinition>>({});
    const activeTrackerIdRef = useRef<string | null>(null);
    const [trackerSchemas, setTrackerSchemas] = useState<Record<string, TrackedObjectDefinition>>({});
    const [activeTrackerId, setActiveTrackerId] = useState<string | null>(null);

    // Service instances
    const wsConnectionRef = useRef<WebSocketConnection | null>(null);
    const frameProcessorRef = useRef<FrameProcessor | null>(null);
    const canvasManagerRef = useRef<CanvasManager | null>(null);
    const framerateStoreRef = useRef<FramerateStore>(new FramerateStore());
    const logStoreRef = useRef<LogStore>(new LogStore());

    // Latest server-side (backend) FPS stored in a ref for non-reactive access
    const serverFpsRef = useRef<number | null>(null);

    // Last-dispatched progress per pipeline — skip dispatch when value is unchanged
    const lastPipelineProgressRef = useRef<Record<string, string>>({});

    // 3D data refs and subscriber sets
    const keypointsRef = useRef<KeypointsFrame | null>(null);
    const keypointsSubscribersRef = useRef<Set<KeypointsCallback>>(new Set());
    const skeletonRef = useRef<KeypointsFrame | null>(null);
    const skeletonSubscribersRef = useRef<Set<KeypointsCallback>>(new Set());
    const centerOfMassSubscribersRef = useRef<Set<(point: Point3d | null) => void>>(new Set());
    const xcomSubscribersRef = useRef<Set<(point: Point3d | null) => void>>(new Set());
    const bodyKinematicsSubscribersRef = useRef<Set<(bk: BodyKinematics | null) => void>>(new Set());

    // Holds the latest binary payload received from the WebSocket.
    const pendingPayloadRef = useRef<ArrayBuffer | null>(null);
    const pendingJsonPayloadRef = useRef<FrontendPayloadMessage | null>(null);
    const pendingKeypointsRef = useRef<ArrayBuffer | null>(null);
    const processingFrameRef = useRef<boolean>(false);
    const frameLoopRef = useRef<number | null>(null);
    const pendingAckFrameNumberRef = useRef<number | null>(null);

    // Cached sorted camera IDs from the last frame
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

        const handleBeforeUnload = (): void => {
            logStoreRef.current?.persistNow();
        };
        window.addEventListener('beforeunload', handleBeforeUnload);

        return () => {
            window.removeEventListener('beforeunload', handleBeforeUnload);
            logStoreRef.current?.dispose();
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
            store.dispatch(wsConnectionChanged(connected));
            setIsFailed(newState === ConnectionState.FAILED);

            if (newState === ConnectionState.DISCONNECTED || newState === ConnectionState.FAILED) {
                canvasManagerRef.current?.terminateAllWorkers();
                frameProcessorRef.current?.reset();
                serverFpsRef.current = null;
                processingFrameRef.current = false;
                pendingPayloadRef.current = null;
                pendingJsonPayloadRef.current = null;
                pendingKeypointsRef.current = null;
                pendingAckFrameNumberRef.current = null;
                lastCameraIdsRef.current = [];
                framerateStoreRef.current.clear();
                keypointsRef.current = null;
                skeletonRef.current = null;
                trackerSchemasRef.current = {};
                activeTrackerIdRef.current = null;
                setTrackerSchemas({});
                setActiveTrackerId(null);
                setConnectedCameraIds([]);
                store.dispatch(serverDisconnected());
            }
        };

        let lastFrontendFrameTime = 0;
        const frontendDurations: number[] = [];

        const dispatchFrames = (
            result: Awaited<ReturnType<FrameProcessor['processFramePayload']>>
        ): void => {
            if (!result) return;

            const {frames, cameraIds} = result;

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
                canvasManagerRef.current?.sendFrameToWorker(
                    frameData.cameraId,
                    frameData.pixelBuffer,
                    frameData.width,
                    frameData.height,
                );
            }

            const now = performance.now();
            if (lastFrontendFrameTime > 0) {
                const dur = now - lastFrontendFrameTime;
                frontendDurations.push(dur);
                if (frontendDurations.length > 30) frontendDurations.shift();
                if (frontendDurations.length >= 2) {
                    let sum = 0, min = Infinity, max = -Infinity;
                    for (const d of frontendDurations) {
                        sum += d;
                        if (d < min) min = d;
                        if (d > max) max = d;
                    }
                    const mean = sum / frontendDurations.length;
                    framerateStoreRef.current.updateFrontend({
                        mean_frame_duration_ms: mean,
                        mean_frames_per_second: mean > 0 ? 1000 / mean : 0,
                        frame_duration_mean: mean,
                        frame_duration_median: mean,
                        frame_duration_min: min,
                        frame_duration_max: max,
                        frame_duration_stddev: 0,
                        frame_duration_coefficient_of_variation: 0,
                        calculation_window_size: frontendDurations.length,
                        framerate_source: 'Display (browser)',
                    });
                }
            }
            lastFrontendFrameTime = now;
        };

        const dispatchJsonPayload = (payload: FrontendPayloadMessage): void => {
            if (payload.charuco_overlays || payload.skeleton_overlays) {
                canvasManagerRef.current?.updateOverlays(
                    payload.charuco_overlays,
                    payload.skeleton_overlays,
                );
            }

            if (payload.center_of_mass) {
                const comPoint: Point3d = {
                    x: (payload.center_of_mass as Point3d).x,
                    y: (payload.center_of_mass as Point3d).y,
                    z: (payload.center_of_mass as Point3d).z,
                };
                for (const cb of centerOfMassSubscribersRef.current) cb(comPoint);
            }

            if (payload.xcom) {
                const xcomPoint: Point3d = {
                    x: (payload.xcom as Point3d).x,
                    y: (payload.xcom as Point3d).y,
                    z: (payload.xcom as Point3d).z,
                };
                for (const cb of xcomSubscribersRef.current) cb(xcomPoint);
            }

            const bodyKinematics = payload.body_kinematics ?? null;
            for (const cb of bodyKinematicsSubscribersRef.current) cb(bodyKinematics);
        };

        const dispatchBinaryKeypoints = (buf: ArrayBuffer): void => {
            const parsed = parseKeypointsMessage(buf);
            for (const block of parsed.blocks) {
                let pointNames: readonly string[] | null = null;
                if (block.pointNames) {
                    pointNames = block.pointNames;
                } else {
                    const schema = trackerSchemasRef.current[block.trackerId];
                    if (!schema) continue;
                    pointNames = schema.tracked_points;
                }

                const interleaved = block.interleaved instanceof Float32Array
                    ? block.interleaved
                    : new Float32Array(block.interleaved);
                const frame: KeypointsFrame = { pointNames, interleaved };

                if (block.kind === BLOCK_KIND.KEYPOINTS_3D) {
                    keypointsRef.current = frame;
                    for (const cb of keypointsSubscribersRef.current) cb(frame);
                } else if (block.kind === BLOCK_KIND.SKELETON_3D) {
                    skeletonRef.current = frame;
                    for (const cb of skeletonSubscribersRef.current) cb(frame);
                }
            }
        };

        let decodeStartTime = 0;
        const processFrameLoop = (): void => {
            if (pendingAckFrameNumberRef.current !== null) {
                ws.send({
                    type: 'frameAcknowledgment',
                    frameNumber: pendingAckFrameNumberRef.current,
                    displayImageSizes: canvasManagerRef.current?.getDisplaySizes(),
                });
                pendingAckFrameNumberRef.current = null;
            }

            if (pendingJsonPayloadRef.current !== null) {
                const jsonPayload = pendingJsonPayloadRef.current;
                pendingJsonPayloadRef.current = null;
                dispatchJsonPayload(jsonPayload);
            }

            if (pendingKeypointsRef.current !== null) {
                const buf = pendingKeypointsRef.current;
                pendingKeypointsRef.current = null;
                try {
                    dispatchBinaryKeypoints(buf);
                } catch (err) {
                    console.error('Error parsing binary keypoints message:', err);
                }
            }

            if (!processingFrameRef.current && pendingPayloadRef.current !== null) {
                const payload = pendingPayloadRef.current;
                pendingPayloadRef.current = null;
                processingFrameRef.current = true;
                decodeStartTime = performance.now();
                frameProcessorRef.current!.processFramePayload(payload)
                    .then(result => {
                        const decodeMs = performance.now() - decodeStartTime;
                        if (decodeMs > 100) console.warn(`decode spike: ${decodeMs.toFixed(1)}ms`);
                        dispatchFrames(result);
                    })
                    .catch(err => console.error('Error processing frame:', err))
                    .finally(() => { processingFrameRef.current = false; });
            }

            frameLoopRef.current = requestAnimationFrame(processFrameLoop);
        };

        frameLoopRef.current = requestAnimationFrame(processFrameLoop);

        const handleMessage = (event: MessageEvent): void => {
            if (event.data instanceof ArrayBuffer) {
                if (isKeypointsMessage(event.data)) {
                    pendingKeypointsRef.current = event.data;
                } else {
                    if (event.data.byteLength >= 16) {
                        const view = new DataView(event.data);
                        pendingAckFrameNumberRef.current = Number(view.getBigInt64(8, true));
                    }
                    pendingPayloadRef.current = event.data;
                }
            }
            else if (typeof event.data === 'string') {
                if (event.data === 'pong') return;

                try {
                    const jsonData = JSON.parse(event.data);

                    if (isLogRecord(jsonData)) {
                        logStoreRef.current.add(jsonData);
                    }
                    else if (isTrackerSchemas(jsonData)) {
                        const schemas = jsonData.schemas;
                        trackerSchemasRef.current = schemas;
                        const keys = Object.keys(schemas);
                        const firstId = keys.length > 0 ? keys[0] : null;
                        activeTrackerIdRef.current = firstId;
                        setTrackerSchemas(schemas);
                        setActiveTrackerId(firstId);
                        canvasManagerRef.current?.setSchema(schemas, firstId);
                    }
                    else if (isFramerateUpdate(jsonData)) {
                        serverFpsRef.current = jsonData.backend_framerate.mean_frames_per_second;
                        framerateStoreRef.current.updateBackend(jsonData.backend_framerate);
                    }
                    else if (isFrontendPayload(jsonData)) {
                        pendingJsonPayloadRef.current = jsonData;
                    } else if (isPosthocProgress(jsonData)) {
                        const PIPELINE_TYPE_MAP: Record<string, PipelineType> = {
                            calibration: PipelineType.CALIBRATION,
                            mocap: PipelineType.MOCAP,
                        };
                        const pipelineType = PIPELINE_TYPE_MAP[jsonData.pipeline_type];
                        if (!pipelineType) {
                            console.error('[WS] Unknown pipeline_type in progress message:', jsonData.pipeline_type, jsonData);
                        } else {
                            const progress = Math.round(jsonData.progress_fraction * 100);
                            const dedupeKey = `${jsonData.phase}:${progress}`;
                            if (lastPipelineProgressRef.current[jsonData.pipeline_id] !== dedupeKey) {
                                lastPipelineProgressRef.current[jsonData.pipeline_id] = dedupeKey;
                                const BACKEND_PHASE_MAP: Record<string, PipelinePhase> = {
                                    queued: PipelinePhase.QUEUED,
                                    setting_up: PipelinePhase.SETTING_UP,
                                    processing_images: PipelinePhase.PROCESSING_VIDEOS,
                                    collecting_camera_output: PipelinePhase.SETTING_UP,
                                    building_recorders: PipelinePhase.AGGREGATING,
                                    triangulating: PipelinePhase.AGGREGATING,
                                    exporting_blender: PipelinePhase.FINALIZING,
                                    validating_observations: PipelinePhase.AGGREGATING,
                                    running_solver: PipelinePhase.AGGREGATING,
                                    saving_calibration: PipelinePhase.FINALIZING,
                                    complete: PipelinePhase.COMPLETE,
                                    failed: PipelinePhase.FAILED,
                                };
                                store.dispatch(pipelineProgressUpdated({
                                    pipelineId: jsonData.pipeline_id,
                                    pipelineType,
                                    phase: BACKEND_PHASE_MAP[jsonData.phase] ?? PipelinePhase.PROCESSING_VIDEOS,
                                    progress,
                                    detail: jsonData.detail,
                                    recordingName: jsonData.recording_name,
                                    recordingPath: jsonData.recording_path,
                                }));
                                if (!jsonData.pipeline_id.includes(':')) {
                                    if (pipelineType === PipelineType.MOCAP) {
                                        store.dispatch({
                                            type: 'mocap/posthocProgressReceived',
                                            payload: {phase: jsonData.phase, progress_fraction: jsonData.progress_fraction, detail: jsonData.detail},
                                        });
                                    } else {
                                        store.dispatch({
                                            type: 'calibration/calibrationPipelineProgressReceived',
                                            payload: {phase: jsonData.phase},
                                        });
                                    }
                                }
                            }
                        }
                    } else if (isAppState(jsonData)) {
                        store.dispatch(serverStateReceived(jsonData));
                    } else {
                        console.warn('[WS] unhandled JSON message:', jsonData.message_type ?? '(no message_type)', jsonData);
                    }
                } catch (error) {
                    console.error('Error parsing JSON message:', error);
                }
            }
        };

        ws.on('state-change', handleStateChange);
        ws.on('message', handleMessage);

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

    const subscribeToKeypoints = useCallback((cb: KeypointsCallback): () => void => {
        keypointsSubscribersRef.current.add(cb);
        return () => { keypointsSubscribersRef.current.delete(cb); };
    }, []);

    const subscribeToSkeleton = useCallback((cb: KeypointsCallback): () => void => {
        skeletonSubscribersRef.current.add(cb);
        return () => { skeletonSubscribersRef.current.delete(cb); };
    }, []);

    const subscribeToCenterOfMass = useCallback((cb: (point: Point3d | null) => void): () => void => {
        centerOfMassSubscribersRef.current.add(cb);
        return () => {
            centerOfMassSubscribersRef.current.delete(cb);
        };
    }, []);

    const subscribeToXcom = useCallback((cb: (point: Point3d | null) => void): () => void => {
        xcomSubscribersRef.current.add(cb);
        return () => {
            xcomSubscribersRef.current.delete(cb);
        };
    }, []);

    const subscribeToBodyKinematics = useCallback((cb: (bk: BodyKinematics | null) => void): () => void => {
        bodyKinematicsSubscribersRef.current.add(cb);
        return () => {
            bodyKinematicsSubscribersRef.current.delete(cb);
        };
    }, []);

    const getLatestKeypoints = useCallback((): KeypointsFrame | null => {
        return keypointsRef.current;
    }, []);

    const getLatestSkeleton = useCallback((): KeypointsFrame | null => {
        return skeletonRef.current;
    }, []);

    const setOverlayVisibility = useCallback((charuco: boolean, skeleton: boolean): void => {
        canvasManagerRef.current?.setOverlayVisibility(charuco, skeleton);
    }, []);

    const getActiveSchema = useCallback((): TrackedObjectDefinition | null => {
        const id = activeTrackerIdRef.current;
        if (!id) return null;
        return trackerSchemasRef.current[id] ?? null;
    }, []);

    const updateServerConnection = useCallback((host: string, port: number): void => {
        const currentUrl = serverUrls.getWebSocketUrl();
        serverUrls.setHost(host);
        serverUrls.setPort(port);
        const newUrl = serverUrls.getWebSocketUrl();
        const ws = wsConnectionRef.current;
        if (ws && newUrl !== currentUrl) {
            ws.disconnect();
            ws.updateUrl(newUrl);
        }
    }, []);

    const contextValue = useMemo(() => ({
        isConnected,
        isFailed,
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
        subscribeToKeypoints,
        subscribeToSkeleton,
        subscribeToCenterOfMass,
        subscribeToXcom,
        subscribeToBodyKinematics,
        getLatestKeypoints,
        getLatestSkeleton,
        setOverlayVisibility,
        trackerSchemas,
        activeTrackerId,
        getActiveSchema,
    }), [isConnected, isFailed, connectedCameraIds, trackerSchemas, activeTrackerId, connect, disconnect, sendWebsocketMessage, setCanvasForCamera, getFps, getServerFps, getFramerateStore, getLogStore, updateServerConnection, subscribeToKeypoints, subscribeToSkeleton, subscribeToCenterOfMass, subscribeToXcom, subscribeToBodyKinematics, getLatestKeypoints, getLatestSkeleton, setOverlayVisibility, getActiveSchema]);

    return (
        <ServerContext.Provider value={contextValue}>
            {children}
        </ServerContext.Provider>
    );
};
