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
import {installConsoleLogBridge} from "@/services/server/server-helpers/console-log-bridge";
import {OverlayManager} from "@/services/server/server-helpers/image-overlay/overlay-renderer-factory";
import {CharucoObservation} from "@/services/server/server-helpers/image-overlay/charuco-types";
import {MediapipeObservation} from "@/services/server/server-helpers/image-overlay/mediapipe-types";
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
    blockToPointDict,
    isKeypointsMessage,
    parseKeypointsMessage,
} from "@/services/server/server-helpers/frame-processor/keypoints-binary-parser";
import {Point3d, RigidBodyPose} from "@/components/viewport3d";
import {store} from "@/store";
import {pipelineProgressUpdated, PipelinePhase, PipelineType} from "@/store/slices/pipelines";

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

    // Tracker schemas — shipped by the backend on WS connect/reconfigure. Held
    // in both a ref (for synchronous access in frame dispatch) and state (for
    // re-rendering renderers that depend on it).
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
    const overlayManagerRef = useRef<OverlayManager | null>(null);

    // Overlay data refs - NO REACT STATE to avoid re-renders!
    const latestCharucoRef = useRef<Map<string, CharucoObservation>>(new Map());
    const latestMediapipeRef = useRef<Map<string, MediapipeObservation>>(new Map());

    // Overlay visibility flags - toggled by UI, applied in dispatchFrames
    const charucoEnabledRef = useRef<boolean>(true);
    const skeletonEnabledRef = useRef<boolean>(true);

    // Latest server-side (backend) FPS stored in a ref for non-reactive access
    const serverFpsRef = useRef<number | null>(null);

    // Last-dispatched progress per pipeline — skip dispatch when value is unchanged
    const lastPipelineProgressRef = useRef<Record<string, number>>({});

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
    const pendingJsonPayloadRef = useRef<FrontendPayloadMessage | null>(null);
    // Latest binary keypoints frame (only when FREEMOCAP_BINARY_KEYPOINTS=1
    // is set on the backend). Older unprocessed frames are overwritten.
    const pendingKeypointsRef = useRef<ArrayBuffer | null>(null);
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

        // const uninstallConsoleBridge = installConsoleLogBridge(logStoreRef.current);

        return () => {
            // uninstallConsoleBridge();
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
                pendingJsonPayloadRef.current = null;
                pendingKeypointsRef.current = null;
                lastCameraIdsRef.current = [];
                framerateStoreRef.current.clear();
                trackedPointsRef.current = {};
                rigidBodiesRef.current = new Map();
                keypointsFilteredRef.current = {};
                latestCharucoRef.current.clear();
                latestMediapipeRef.current.clear();
                overlayManagerRef.current?.clearAll();
                trackerSchemasRef.current = {};
                activeTrackerIdRef.current = null;
                setTrackerSchemas({});
                setActiveTrackerId(null);
                setConnectedCameraIds([]);
            }
        };

        let lastFrontendFrameTime = 0;
        const frontendDurations: number[] = [];

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

            // Composite overlays onto frames and dispatch to canvas workers in parallel.
            const overlayManager = overlayManagerRef.current!;
            await Promise.all(frames.map(async (frameData) => {
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
            }));

            if (frameNumbers.size > 0) {
                const maxFrameNumber = Math.max(...Array.from(frameNumbers));
                ws.send({type: 'frameAcknowledgment', frameNumber: maxFrameNumber});
            }

            // Measure display fps from decoded frame arrivals — fires every frame
            // regardless of pipeline state, so the framerate panel always has data.
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

        // Dispatches a buffered frontend_payload to all 3D-scene subscribers.
        // Called from the rAF loop (not from the WebSocket handler) so subscriber
        // work happens during the animation frame, not mid-message-storm.
        const dispatchJsonPayload = (payload: FrontendPayloadMessage): void => {
            if (payload.charuco_overlays) {
                for (const [cameraId, charuco] of Object.entries(payload.charuco_overlays)) {
                    latestCharucoRef.current.set(cameraId, charuco as CharucoObservation);
                }
            }
            if (payload.skeleton_overlays) {
                for (const [cameraId, skeleton] of Object.entries(payload.skeleton_overlays)) {
                    latestMediapipeRef.current.set(cameraId, skeleton as MediapipeObservation);
                }
            }

            if (payload.keypoints_raw) {
                trackedPointsRef.current = payload.keypoints_raw as Record<string, Point3d>;
                for (const cb of trackedPointsSubscribersRef.current) {
                    cb(trackedPointsRef.current);
                }
            }

            if (payload.keypoints_filtered) {
                keypointsFilteredRef.current = payload.keypoints_filtered as Record<string, Point3d>;
                for (const cb of keypointsFilteredSubscribersRef.current) {
                    cb(keypointsFilteredRef.current);
                }
            }

            if (payload.rigid_body_poses) {
                const posesMap = new Map<string, RigidBodyPose>();
                for (const [key, pose] of Object.entries(payload.rigid_body_poses)) {
                    posesMap.set(key, pose as RigidBodyPose);
                }
                rigidBodiesRef.current = posesMap;
                for (const cb of rigidBodiesSubscribersRef.current) cb(posesMap);
            }
        };

        // Decode the binary keypoints message (when FREEMOCAP_BINARY_KEYPOINTS
        // is enabled on the backend) and dispatch to the same subscribers as
        // the JSON path. Step 1 of the refactor preserves the legacy
        // Record<string, Point3d> shape so the renderer contract is unchanged.
        const dispatchBinaryKeypoints = (buf: ArrayBuffer): void => {
            const parsed = parseKeypointsMessage(buf);
            for (const block of parsed.blocks) {
                const schema = trackerSchemasRef.current[block.trackerId];
                if (!schema) {
                    // Schema handshake hasn't arrived yet, or the backend is
                    // shipping a tracker we don't know about. Drop silently —
                    // the next frame after the handshake will populate.
                    continue;
                }
                const dict = blockToPointDict(block, schema.tracked_points);
                if (block.kind === BLOCK_KIND.KEYPOINTS_RAW_3D) {
                    trackedPointsRef.current = dict;
                    for (const cb of trackedPointsSubscribersRef.current) cb(dict);
                } else if (block.kind === BLOCK_KIND.KEYPOINTS_FILTERED_3D) {
                    keypointsFilteredRef.current = dict;
                    for (const cb of keypointsFilteredSubscribersRef.current) cb(dict);
                }
            }
        };

        // rAF-driven processing loop. Non-async so the next rAF is always
        // registered immediately — the async decode+dispatch chain runs via
        // .then() and never blocks rAF re-registration.
        let lastRafTime = 0;
        let decodeStartTime = 0;
        const processFrameLoop = (): void => {
            const now = performance.now();
            const rafGap = lastRafTime > 0 ? now - lastRafTime : 0;
            lastRafTime = now;
            if (rafGap > 50) {
                // Still decoding from last frame? Gap is decode-caused. Otherwise it's main-thread jank (R3F, GC, etc.).
                const tag = processingFrameRef.current
                    ? `decode-busy (started ${(now - decodeStartTime).toFixed(1)}ms ago)`
                    : 'main-thread jank';
                console.warn(`rAF gap: ${rafGap.toFixed(1)}ms [${tag}]`);
            }

            // Dispatch buffered JSON payload (keypoints, overlays, rigid bodies).
            // Processed here rather than in the WebSocket handler to keep the
            // handler minimal and move subscriber work into the animation frame.
            if (pendingJsonPayloadRef.current !== null) {
                const jsonPayload = pendingJsonPayloadRef.current;
                pendingJsonPayloadRef.current = null;
                dispatchJsonPayload(jsonPayload);
            }

            // Decode any buffered binary keypoints frame after the JSON
            // payload — when both are present for the same frame the binary
            // copy is authoritative for keypoints (the backend already nulls
            // those JSON fields when binary is active, but order it this way
            // anyway so a stray JSON copy can't clobber the binary one).
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
                        if (decodeMs > 20) console.warn(`decode spike: ${decodeMs.toFixed(1)}ms`);
                        return dispatchFrames(result);
                    })
                    .catch(err => console.error('Error processing frame:', err))
                    .finally(() => { processingFrameRef.current = false; });
            }
            frameLoopRef.current = requestAnimationFrame(processFrameLoop);
        };

        frameLoopRef.current = requestAnimationFrame(processFrameLoop);

        const handleMessage = (event: MessageEvent): void => {
            // Handle binary frame data: demux on the first byte. Image frames
            // start with MessageType.PAYLOAD_HEADER (0); keypoints messages
            // start with KEYPOINTS_PAYLOAD_HEADER (3). Older unprocessed
            // payloads of either kind are overwritten (frame dropping).
            if (event.data instanceof ArrayBuffer) {
                if (isKeypointsMessage(event.data)) {
                    pendingKeypointsRef.current = event.data;
                } else {
                    pendingPayloadRef.current = event.data;
                }
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
                        // Handle tracker schema handshake (sent once on connect,
                        // or again when the pipeline reconfigures). Passed straight
                    // through to the 2D overlay renderer via OverlayManager.
                    else if (isTrackerSchemas(jsonData)) {
                        const schemas = jsonData.schemas;
                        trackerSchemasRef.current = schemas;
                        const keys = Object.keys(schemas);
                        const firstId = keys.length > 0 ? keys[0] : null;
                        activeTrackerIdRef.current = firstId;
                        setTrackerSchemas(schemas);
                        setActiveTrackerId(firstId);
                        overlayManagerRef.current?.setTrackerSchemas(schemas, firstId ?? undefined);
                    }
                    // Handle framerate updates — backend_framerate stored; frontend_framerate
                    // is now measured locally in dispatchJsonPayload so we skip it here.
                    else if (isFramerateUpdate(jsonData)) {
                        serverFpsRef.current = jsonData.backend_framerate.mean_frames_per_second;
                        framerateStoreRef.current.updateBackend(jsonData.backend_framerate);
                    }
                    // Buffer frontend_payload for dispatch in the rAF loop.
                    // Older unprocessed payloads are overwritten (keep latest only).
                    else if (isFrontendPayload(jsonData)) {
                        pendingJsonPayloadRef.current = jsonData;
                    } else if (isPosthocProgress(jsonData)) {

                        const progress = Math.round(jsonData.progress_fraction * 100);
                        if (lastPipelineProgressRef.current[jsonData.pipeline_id] !== progress) {
                            lastPipelineProgressRef.current[jsonData.pipeline_id] = progress;
                            const BACKEND_PHASE_MAP: Record<string, PipelinePhase> = {
                                collecting_frames: PipelinePhase.SETTING_UP,
                                detecting_frames: PipelinePhase.PROCESSING_VIDEOS,
                                all_frames_collected: PipelinePhase.AGGREGATING,
                                processing: PipelinePhase.AGGREGATING,
                                running_task: PipelinePhase.AGGREGATING,
                                complete: PipelinePhase.COMPLETE,
                                failed: PipelinePhase.FAILED,
                            };
                            store.dispatch(pipelineProgressUpdated({
                                pipelineId: jsonData.pipeline_id,
                                pipelineType: PipelineType.MOCAP, // TODO: backend should send type
                                phase: BACKEND_PHASE_MAP[jsonData.phase] ?? PipelinePhase.PROCESSING_VIDEOS,
                                progress,
                                detail: jsonData.detail,
                            }));
                        }
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
        return () => {
            trackedPointsSubscribersRef.current.delete(cb);
        };
    }, []);

    const subscribeToKeypointsFiltered = useCallback((cb: (points: Record<string, Point3d>) => void): () => void => {
        keypointsFilteredSubscribersRef.current.add(cb);
        return () => {
            keypointsFilteredSubscribersRef.current.delete(cb);
        };
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

    const getActiveSchema = useCallback((): TrackedObjectDefinition | null => {
        const id = activeTrackerIdRef.current;
        if (!id) return null;
        return trackerSchemasRef.current[id] ?? null;
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
        trackerSchemas,
        activeTrackerId,
        getActiveSchema,
    }), [isConnected, connectedCameraIds, trackerSchemas, activeTrackerId, connect, disconnect, sendWebsocketMessage, setCanvasForCamera, getFps, getServerFps, getFramerateStore, getLogStore, updateServerConnection, subscribeToKeypointsRaw, subscribeToKeypointsFiltered, subscribeToRigidBodies, getLatestKeypointsRaw, setOverlayVisibility, getActiveSchema]);

    return (
        <ServerContext.Provider value={contextValue}>
            {children}
        </ServerContext.Provider>
    );
};
