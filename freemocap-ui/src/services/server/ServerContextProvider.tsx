// ServerContextProvider.tsx
//
// Thin consumer of TransportService. TransportService owns the WebSocket, the
// CBOR decode, and the kind-keyed dispatch; this provider subscribes to it and
// owns the Redux dispatch + frame/image rendering. It retains:
//   - the inbound frameAcknowledgment (displayImageSizes) send loop;
//   - the FrameProcessor / CanvasManager wiring (per-camera image + overlay);
//   - the subscriber-hook surface (now backed by TransportService subscribers);

import React, {ReactNode, useCallback, useEffect, useMemo, useRef, useState} from 'react';
import { ServerContext, type ServerContextValue } from './server-context';
export { useServer, useServerOptional, ServerContext, type ServerContextValue } from './server-context';

import {ConnectionState} from "@/services/server/server-helpers/websocket-connection";
import {FrameProcessor} from "@/services/server/server-helpers/frame-processor/frame-processor";
import {CanvasManager} from "@/services/server/server-helpers/canvas-manager";
import {serverUrls} from "@/services";
import {FramerateStore} from "@/services/server/server-helpers/framerate-store";
import {LogStore} from "@/services/server/server-helpers/log-store";
import {Point3d, BodyKinematics} from "@/components/viewport3d";
import {
    KeypointsCallback,
    KeypointsFrame,
} from "@/components/viewport3d/KeypointsSourceContext";
import {store} from "@/store";
import {pipelineProgressUpdated, PipelinePhase, PipelineType} from "@/store/slices/pipelines";
import {serverStateReceived, wsConnectionChanged, serverDisconnected} from "@/store/slices/connection/connection-slice";
import {modelsReceived} from "@/store/slices/model";
import {conventionReceived} from "@/store/slices/convention";
import {camerasReceived} from "@/store/slices/camera-layout";
import {loadCalibrationForRecording} from "@/store/slices/calibration";
import {TransportService} from "@/services/server/transport/TransportService";
import {
    OverlayLayer,
    type RotationsFrame,
    type RollingChannelName,
    type SegmentLengthsFrame,
} from "@/services/server/transport/frame-types";
import type {
    CalibratedCamera,
    ModelDefinition,
    ProgressMessage,
} from "@/services/server/transport/message-contract";
import type {SkeletonObservation} from "@/services/server/server-helpers/image-overlay";

// Compare two already-sorted string arrays without allocating
function sortedArraysEqual(a: string[], b: string[]): boolean {
    if (a.length !== b.length) return false;
    for (let i = 0; i < a.length; i++) {
        if (a[i] !== b[i]) return false;
    }
    return true;
}

export const ServerContextProvider: React.FC<{ children: ReactNode }> = ({children}) => {
    const [isConnected, setIsConnected] = useState<boolean>(false);
    const [isFailed, setIsFailed] = useState<boolean>(false);
    const [connectedCameraIds, setConnectedCameraIds] = useState<string[]>([]);

    // Service instances
    const transportRef = useRef<TransportService | null>(null);
    const frameProcessorRef = useRef<FrameProcessor | null>(null);
    const canvasManagerRef = useRef<CanvasManager | null>(null);
    const framerateStoreRef = useRef<FramerateStore>(new FramerateStore());
    const logStoreRef = useRef<LogStore>(new LogStore());

    const serverFpsRef = useRef<number | null>(null);
    const lastPipelineProgressRef = useRef<Record<string, string>>({});

    // Held model/cameras (for overlay image sizes + connections).
    const modelsRef = useRef<ModelDefinition[] | null>(null);
    const camerasRef = useRef<CalibratedCamera[] | null>(null);

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

    const pendingPayloadRef = useRef<ArrayBuffer | null>(null);
    const processingFrameRef = useRef<boolean>(false);
    const pendingAckFrameNumberRef = useRef<number | null>(null);
    const frameLoopRef = useRef<number | null>(null);
    const pendingOverlaysRef = useRef<Map<number, Map<string, SkeletonObservation>>>(new Map());

    const lastCameraIdsRef = useRef<string[]>([]);

    // Initialize services once
    useEffect(() => {
        transportRef.current = new TransportService({
            url: serverUrls.getWebSocketUrl(),
            maxWindowFrames: 100,
        });
        frameProcessorRef.current = new FrameProcessor();
        canvasManagerRef.current = new CanvasManager();

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
            if (overlay.layer !== OverlayLayer.DETECTIONS && overlay.layer !== OverlayLayer.REPROJECTIONS) return;
            const dims = overlay.imageSize
                ?? camerasRef.current?.find((c) => c.id === overlay.cameraId)?.image_size;
            const frameOverlays = pendingOverlaysRef.current.get(overlay.frameNumber)
                ?? new Map<string, SkeletonObservation>();
            const observation: SkeletonObservation = frameOverlays.get(overlay.cameraId) ?? {
                camera_id: overlay.cameraId,
                frame_number: overlay.frameNumber,
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
                observation.connections = modelsRef.current?.[0]?.connections ?? [];
            }
            frameOverlays.set(overlay.cameraId, observation);
            pendingOverlaysRef.current.set(overlay.frameNumber, frameOverlays);
        }));
        subs.push(transport.subscribeToSegmentLengths((frame) => {
            segmentLengthsRef.current = frame;
        }));

        // Static-model + kind subscribers → Redux (change-detected on the transport).
        subs.push(transport.subscribeToModels((models) => {
            modelsRef.current = models;
            store.dispatch(modelsReceived(models));
        }));
        subs.push(transport.subscribeToConvention((convention) => {
            store.dispatch(conventionReceived(convention));
        }));
        subs.push(transport.subscribeToCameras((cameras) => {
            camerasRef.current = cameras;
            store.dispatch(camerasReceived(cameras));
        }));
        subs.push(transport.subscribeToLog((record) => {
            logStoreRef.current.add(record);
        }));
        subs.push(transport.subscribeToFramerate((message) => {
            serverFpsRef.current = message.backend_framerate.mean_frames_per_second;
            framerateStoreRef.current.updateBackend(message.backend_framerate);
            framerateStoreRef.current.updateFrontend(message.frontend_framerate);
        }));
        subs.push(transport.subscribeToAppState((message) => {
            store.dispatch(serverStateReceived(message));
        }));
        subs.push(transport.subscribeToProgress((message) => handleProgress(message, lastPipelineProgressRef)));

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

    // Wire connection state + frame/image rendering.
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
                modelsRef.current = null;
                camerasRef.current = null;
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
        return () => { centerOfMassSubscribersRef.current.delete(cb); };
    }, []);

    const subscribeToXcom = useCallback((cb: (point: Point3d | null) => void): () => void => {
        xcomSubscribersRef.current.add(cb);
        return () => { xcomSubscribersRef.current.delete(cb); };
    }, []);

    const subscribeToBodyKinematics = useCallback((cb: (bk: BodyKinematics | null) => void): () => void => {
        bodyKinematicsSubscribersRef.current.add(cb);
        return () => { bodyKinematicsSubscribersRef.current.delete(cb); };
    }, []);

    const subscribeToRotations = useCallback((cb: (frame: RotationsFrame) => void): () => void => {
        rotationsSubscribersRef.current.add(cb);
        return () => { rotationsSubscribersRef.current.delete(cb); };
    }, []);

    const subscribeToModels = useCallback((cb: (models: ModelDefinition[]) => void): () => void => {
        return transportRef.current?.subscribeToModels(cb) ?? (() => {});
    }, []);

    const getModels = useCallback((): ModelDefinition[] | null => {
        return transportRef.current?.getModels() ?? null;
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
        subscribeToRotations,
        getLatestRotations,
        getLatestSegmentLengths,
        getRollingWindow,
        subscribeToModels,
        getModels,
    }), [isConnected, isFailed, connectedCameraIds, connect, disconnect, sendWebsocketMessage, setCanvasForCamera, getFps, getServerFps, getFramerateStore, getLogStore, updateServerConnection, subscribeToKeypoints, subscribeToSkeleton, subscribeToCenterOfMass, subscribeToXcom, subscribeToBodyKinematics, getLatestKeypoints, getLatestSkeleton, setOverlayVisibility, subscribeToRotations, getLatestRotations, getLatestSegmentLengths, getRollingWindow, subscribeToModels, getModels]);

    return (
        <ServerContext.Provider value={contextValue}>
            {children}
        </ServerContext.Provider>
    );
};

// Progress → pipeline slices (moved here from the old JSON if/else chain).
function handleProgress(message: ProgressMessage, dedupeRef: { current: Record<string, string> }): void {
    const PIPELINE_TYPE_MAP: Record<string, PipelineType> = {
        calibration: PipelineType.CALIBRATION,
        mocap: PipelineType.MOCAP,
    };
    const pipelineType = PIPELINE_TYPE_MAP[message.pipeline_type];
    if (!pipelineType) {
        console.error('[WS] Unknown pipeline_type in progress message:', message.pipeline_type, message);
        return;
    }
    const progress = Math.round(message.progress_fraction * 100);
    const dedupeKey = message.phase + ':' + progress;
    if (dedupeRef.current[message.pipeline_id] === dedupeKey) return;
    dedupeRef.current[message.pipeline_id] = dedupeKey;

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
        pipelineId: message.pipeline_id,
        pipelineType,
        phase: BACKEND_PHASE_MAP[message.phase] ?? PipelinePhase.PROCESSING_VIDEOS,
        progress,
        detail: message.detail,
        recordingName: message.recording_name,
        recordingPath: message.recording_path,
    }));
    if (!message.pipeline_id.includes(':')) {
        if (pipelineType === PipelineType.MOCAP) {
            store.dispatch({
                type: 'mocap/posthocProgressReceived',
                payload: {phase: message.phase, progress_fraction: message.progress_fraction, detail: message.detail},
            });
        } else {
            store.dispatch({
                type: 'calibration/calibrationPipelineProgressReceived',
                payload: {phase: message.phase},
            });
            if (message.phase === 'complete' && message.recording_name) {
                const recordingPath: string = message.recording_path ?? '';
                const recordingName: string = message.recording_name;
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


