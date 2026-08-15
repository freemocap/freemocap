// ServerContextProvider.tsx
//
// Thin consumer of TransportService. The socket ownership, binary first-byte
// demux, standard-stream schema/sample decode, and rolling-window stores live
// in TransportService. One sample per frame carries the pose, the overlays,
// AND the IMAGE_JPEG camera images — this provider feeds the image bytes into
// the FrameProcessor (decode) and the CanvasManager (per-camera display +
// overlay composite), and retains:
//   - the inbound/redux JSON routing (settings, framerate, posthoc progress,
//     app_state, logs) — the server still routes these over the WS;
//   - the subscriber-hook surface (now backed by TransportService subscribers).

import React, {ReactNode, useCallback, useEffect, useMemo, useRef, useState} from 'react';
import { ServerContext, type ServerContextValue } from './server-context';
export { useServer, useServerOptional, ServerContext, type ServerContextValue } from './server-context';

import {ConnectionState} from "@/services/server/server-helpers/websocket-connection";
import {FrameProcessor} from "@/services/server/server-helpers/frame-processor/frame-processor";
import {CanvasManager} from "@/services/server/server-helpers/canvas-manager";
import {serverUrls} from "@/services";
import {FramerateStore} from "@/services/server/server-helpers/framerate-store";
import {LogStore} from "@/services/server/server-helpers/log-store";
import {
    isFramerateUpdate,
    isLogRecord,
    isPosthocProgress,
    isTrackerSchemas,
} from "@/services/server/server-helpers/websocket-message-types";
import {TrackedObjectDefinition} from "@/services/server/server-helpers/tracked-object-definition";
import {Point3d, BodyKinematics} from "@/components/viewport3d";
import {
    KeypointsCallback,
    KeypointsFrame,
} from "@/components/viewport3d/KeypointsSourceContext";
import {store} from "@/store";
import {pipelineProgressUpdated, PipelinePhase, PipelineType} from "@/store/slices/pipelines";
import {serverStateReceived, wsConnectionChanged, serverDisconnected} from "@/store/slices/connection/connection-slice";
import type {AppStateMessage} from "@/store/slices/connection/connection-types";
import {loadCalibrationForRecording} from "@/store/slices/calibration";
import {TransportService} from "@/services/server/transport/TransportService";
import type {RotationsFrame, RollingChannelName, SegmentLengthsFrame, StreamSchema} from "@/services/server/transport/types";
import {OverlayLayer} from "@/services/server/transport/types";
import type {SkeletonObservation} from "@/services/server/server-helpers/image-overlay";

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
    const transportRef = useRef<TransportService | null>(null);
    const frameProcessorRef = useRef<FrameProcessor | null>(null);
    const canvasManagerRef = useRef<CanvasManager | null>(null);
    const framerateStoreRef = useRef<FramerateStore>(new FramerateStore());
    const logStoreRef = useRef<LogStore>(new LogStore());

    // Latest server-side (backend) FPS stored in a ref for non-reactive access
    const serverFpsRef = useRef<number | null>(null);

    // Last-dispatched progress per pipeline — skip dispatch when value is unchanged
    const lastPipelineProgressRef = useRef<Record<string, string>>({});

    // 3D data refs and subscriber sets (backed by TransportService below).
    const keypointsRef = useRef<KeypointsFrame | null>(null);
    const keypointsSubscribersRef = useRef<Set<KeypointsCallback>>(new Set());
    const skeletonRef = useRef<KeypointsFrame | null>(null);
    const skeletonSubscribersRef = useRef<Set<KeypointsCallback>>(new Set());
    const centerOfMassSubscribersRef = useRef<Set<(point: Point3d | null) => void>>(new Set());
    const xcomSubscribersRef = useRef<Set<(point: Point3d | null) => void>>(new Set());
    const bodyKinematicsSubscribersRef = useRef<Set<(bk: BodyKinematics | null) => void>>(new Set());
    const rotationsRef = useRef<RotationsFrame | null>(null);
    const rotationsSubscribersRef = useRef<Set<(frame: RotationsFrame) => void>>(new Set());
    const segmentLengthsRef = useRef<SegmentLengthsFrame | null>(null);

    // Holds the latest binary JPEG payload received from the WebSocket.
    const pendingPayloadRef = useRef<ArrayBuffer | null>(null);
    const processingFrameRef = useRef<boolean>(false);
    const pendingAckFrameNumberRef = useRef<number | null>(null);
    const frameLoopRef = useRef<number | null>(null);
    // Overlay observations keyed by frame number, then camera id — the image
    // and its overlay for frame N arrive in the same sample, and the decode is
    // async, so the observation is matched to the frame by number.
    const pendingOverlaysRef = useRef<Map<number, Map<string, SkeletonObservation>>>(new Map());

    // Cached sorted camera IDs from the last frame
    const lastCameraIdsRef = useRef<string[]>([]);

    // Initialize services once
    useEffect(() => {
        transportRef.current = new TransportService({
            url: serverUrls.getWebSocketUrl(),
            maxWindowFrames: 100,
        });
        frameProcessorRef.current = new FrameProcessor();
        canvasManagerRef.current = new CanvasManager();

        // Fan standard-stream sample subscribers out to the legacy subscriber sets.
        const subs: (() => void)[] = [];
        const transport = transportRef.current;
        subs.push(transport.subscribeToKeypoints((frame) => {
            const kf: KeypointsFrame = { pointNames: frame.names, interleaved: frame.data };
            keypointsRef.current = kf;
            for (const cb of keypointsSubscribersRef.current) cb(kf);
        }));
        subs.push(transport.subscribeToSegmentOrigins((frame) => {
            const kf: KeypointsFrame = { pointNames: frame.names, interleaved: frame.data };
            skeletonRef.current = kf;
            for (const cb of skeletonSubscribersRef.current) cb(kf);
        }));
        subs.push(transport.subscribeToDerivedPoints((derived) => {
            const com = derived.centerOfMass;
            const xcom = derived.xcom;
            for (const cb of centerOfMassSubscribersRef.current) {
                cb(com ? { x: com[0], y: com[1], z: com[2] } : null);
            }
            for (const cb of xcomSubscribersRef.current) {
                cb(xcom ? { x: xcom[0], y: xcom[1], z: xcom[2] } : null);
            }
        }));
        subs.push(transport.subscribeToRotations((frame) => {
            rotationsRef.current = frame;
            for (const cb of rotationsSubscribersRef.current) cb(frame);
        }));
        subs.push(transport.subscribeToOverlay((overlay) => {
            // Per-camera 2D overlays, in capture-resolution px (the schema
            // carries each camera's capture size so the renderer scales to
            // the display bitmap). DETECTIONS = tracker keypoints (small
            // dots); REPROJECTIONS = the fitted skeleton's segment-origin
            // landmarks (larger dots + segment connections). Both layers of
            // one sample merge into ONE observation, keyed by frame number —
            // dispatchFrames pairs the decoded frame with its own sample.
            if (overlay.layer !== OverlayLayer.DETECTIONS && overlay.layer !== OverlayLayer.REPROJECTIONS) return;
            const dims = transport.getSchema()?.camera_image_sizes[overlay.cameraId];
            const frameOverlays = pendingOverlaysRef.current.get(overlay.frameNumber)
                ?? new Map<string, SkeletonObservation>();
            const observation: SkeletonObservation = frameOverlays.get(overlay.cameraId) ?? {
                message_type: 'skeleton_overlay',
                camera_id: overlay.cameraId,
                frame_number: overlay.frameNumber,
                tracker_id: activeTrackerIdRef.current ?? 'RTMPoseTracker',
                image_width: dims?.[0] ?? 0,
                image_height: dims?.[1] ?? 0,
                points: [],
            };
            const points = overlay.names.map((name, i) => ({
                name,
                x: overlay.data[i * 3],
                y: overlay.data[i * 3 + 1],
                z: 0,
                visibility: overlay.data[i * 3 + 2],
            }));
            if (overlay.layer === OverlayLayer.DETECTIONS) {
                observation.points = points;
            } else {
                observation.landmarks = points;
                observation.connections = transport.getSchema()?.connections ?? [];
            }
            frameOverlays.set(overlay.cameraId, observation);
            pendingOverlaysRef.current.set(overlay.frameNumber, frameOverlays);
        }));
        subs.push(transport.subscribeToSegmentLengths((frame) => {
            segmentLengthsRef.current = frame;
        }));

        const handleBeforeUnload = (): void => {
            logStoreRef.current?.persistNow();
        };
        window.addEventListener('beforeunload', handleBeforeUnload);

        return () => {
            for (const unsub of subs) unsub();
            window.removeEventListener('beforeunload', handleBeforeUnload);
            logStoreRef.current?.dispose();
            if (transportRef.current) {
                transportRef.current.disconnect();
                transportRef.current = null;
            }
            if (canvasManagerRef.current) {
                canvasManagerRef.current.terminateAllWorkers();
            }
            if (frameProcessorRef.current) {
                frameProcessorRef.current.reset();
            }
        };
    }, []);

    // Wire connection state + message routing to the transport service.
    useEffect(() => {
        const transport = transportRef.current;
        if (!transport) return;

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
                pendingAckFrameNumberRef.current = null;
                pendingOverlaysRef.current.clear();
                lastCameraIdsRef.current = [];
                framerateStoreRef.current.clear();
                keypointsRef.current = null;
                skeletonRef.current = null;
                rotationsRef.current = null;
                segmentLengthsRef.current = null;
                trackerSchemasRef.current = {};
                activeTrackerIdRef.current = null;
                setTrackerSchemas({});
                setActiveTrackerId(null);
                setConnectedCameraIds([]);
                transport.reset();
                store.dispatch(serverDisconnected());
            }
        };

        const dispatchFrames = (
            result: Awaited<ReturnType<FrameProcessor['processFramePayload']>>,
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
                const overlay = pendingOverlaysRef.current.get(frameData.frameNumber)?.get(frameData.cameraId) ?? null;
                // Prune overlay entries older than a few frames — they are
                // consumed at most once and the map must not grow.
                for (const key of pendingOverlaysRef.current.keys()) {
                    if (key < frameData.frameNumber - 5) pendingOverlaysRef.current.delete(key);
                }
                canvasManagerRef.current?.sendFrameToWorker(
                    frameData.cameraId,
                    frameData.pixelBuffer,
                    frameData.width,
                    frameData.height,
                    overlay,
                );
            }
        };

        // JSON messages that aren't the standard-stream schema still route here.
        transport.on('message', (event: MessageEvent) => {
            if (typeof event.data !== 'string') return undefined;
            if (event.data === 'pong') return undefined;

            let jsonData: any;
            try {
                jsonData = JSON.parse(event.data);
            } catch {
                return undefined;
            }

            if (isLogRecord(jsonData)) {
                logStoreRef.current.add(jsonData);
            } else if (isTrackerSchemas(jsonData)) {
                const schemas = jsonData.schemas;
                trackerSchemasRef.current = schemas;
                const keys = Object.keys(schemas);
                const firstId = keys.length > 0 ? keys[0] : null;
                activeTrackerIdRef.current = firstId;
                setTrackerSchemas(schemas);
                setActiveTrackerId(firstId);
                canvasManagerRef.current?.setSchema(schemas, firstId);
            } else if (isFramerateUpdate(jsonData)) {
                serverFpsRef.current = jsonData.backend_framerate.mean_frames_per_second;
                framerateStoreRef.current.updateBackend(jsonData.backend_framerate);
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
                                if (jsonData.phase === 'complete' && jsonData.recording_name) {
                                    const recordingPath: string = jsonData.recording_path ?? '';
                                    const recordingName: string = jsonData.recording_name;
                                    const parentDir = recordingPath.endsWith(recordingName)
                                        ? recordingPath.slice(0, recordingPath.length - recordingName.length - 1)
                                        : null;
                                    store.dispatch(loadCalibrationForRecording({
                                        recordingId: recordingName,
                                        recordingParentDirectory: parentDir,
                                    }));
                                }
                            }
                        }
                    }
                }
            } else if (isAppState(jsonData)) {
                store.dispatch(serverStateReceived(jsonData));
            } else if (jsonData.message_type !== 'stream_schema') {
                console.warn('[WS] unhandled JSON message:', jsonData.message_type ?? '(no message_type)', jsonData);
            }
            return undefined;
        });

        // The IMAGE_JPEG block bytes for frame N arrive in the same sample as
        // frame N's overlays — feed them to the frame processor and ack with
        // the sample's own frame number.
        transport.subscribeToImages((buf, frameNumber) => {
            pendingAckFrameNumberRef.current = frameNumber;
            pendingPayloadRef.current = buf;
        });

        const processFrameLoop = (): void => {
            if (pendingAckFrameNumberRef.current !== null) {
                transport.send({
                    type: 'frameAcknowledgment',
                    frameNumber: pendingAckFrameNumberRef.current,
                    displayImageSizes: canvasManagerRef.current?.getDisplaySizes(),
                });
                pendingAckFrameNumberRef.current = null;
            }

            if (!processingFrameRef.current && pendingPayloadRef.current !== null) {
                const payload = pendingPayloadRef.current;
                pendingPayloadRef.current = null;
                processingFrameRef.current = true;
                frameProcessorRef.current!.processFramePayload(payload)
                    .then(result => dispatchFrames(result))
                    .catch(err => console.error('Error processing frame:', err))
                    .finally(() => { processingFrameRef.current = false; });
            }

            frameLoopRef.current = requestAnimationFrame(processFrameLoop);
        };

        frameLoopRef.current = requestAnimationFrame(processFrameLoop);

        transport.on('state-change', handleStateChange);

        return () => {
            transport.off('state-change', handleStateChange);
            transport.disconnect();
            if (frameLoopRef.current !== null) {
                cancelAnimationFrame(frameLoopRef.current);
                frameLoopRef.current = null;
            }
        };
    }, []);

    const connect = useCallback((): void => {
        transportRef.current?.connect();
    }, []);

    const disconnect = useCallback((): void => {
        transportRef.current?.disconnect();
    }, []);

    const sendWebsocketMessage = useCallback((data: string | object): void => {
        transportRef.current?.send(data);
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

    const subscribeToRotations = useCallback((cb: (frame: RotationsFrame) => void): () => void => {
        rotationsSubscribersRef.current.add(cb);
        return () => {
            rotationsSubscribersRef.current.delete(cb);
        };
    }, []);

    const subscribeToSchema = useCallback((cb: (schema: StreamSchema) => void): () => void => {
        return transportRef.current?.subscribeToSchema(cb) ?? (() => {});
    }, []);

    const getStreamSchema = useCallback((): StreamSchema | null => {
        return transportRef.current?.getSchema() ?? null;
    }, []);

    const getLatestKeypoints = useCallback((): KeypointsFrame | null => {
        return keypointsRef.current;
    }, []);

    const getLatestSkeleton = useCallback((): KeypointsFrame | null => {
        return skeletonRef.current;
    }, []);

    const getLatestRotations = useCallback((): RotationsFrame | null => {
        return rotationsRef.current;
    }, []);

    const getLatestSegmentLengths = useCallback((): SegmentLengthsFrame | null => {
        return segmentLengthsRef.current;
    }, []);

    const getRollingWindow = useCallback((channelName: RollingChannelName): unknown[] => {
        return transportRef.current?.getRollingWindow(channelName) ?? [];
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
        const transport = transportRef.current;
        if (transport && newUrl !== currentUrl) {
            transport.updateUrl(newUrl);
            transport.disconnect();
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
        subscribeToRotations,
        getLatestRotations,
        getLatestSegmentLengths,
        getRollingWindow,
        subscribeToSchema,
        getStreamSchema,
    }), [isConnected, isFailed, connectedCameraIds, trackerSchemas, activeTrackerId, connect, disconnect, sendWebsocketMessage, setCanvasForCamera, getFps, getServerFps, getFramerateStore, getLogStore, updateServerConnection, subscribeToKeypoints, subscribeToSkeleton, subscribeToCenterOfMass, subscribeToXcom, subscribeToBodyKinematics, getLatestKeypoints, getLatestSkeleton, setOverlayVisibility, getActiveSchema, subscribeToRotations, getLatestRotations, getLatestSegmentLengths, getRollingWindow, subscribeToSchema, getStreamSchema]);

    return (
        <ServerContext.Provider value={contextValue}>
            {children}
        </ServerContext.Provider>
    );
};
