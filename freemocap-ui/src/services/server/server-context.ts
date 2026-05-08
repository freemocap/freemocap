import { createContext, useContext } from 'react';
import type { FramerateStore } from './server-helpers/framerate-store';
import type { LogStore } from './server-helpers/log-store';
import type { TrackedObjectDefinition } from './server-helpers/tracked-object-definition';
import type { RigidBodyPose } from '@/components/viewport3d';
import type { KeypointsCallback, KeypointsFrame } from '@/components/viewport3d/KeypointsSourceContext';

export interface ServerContextValue {
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
    subscribeToKeypointsRaw: (cb: KeypointsCallback) => () => void;
    subscribeToKeypointsFiltered: (cb: KeypointsCallback) => () => void;
    subscribeToRigidBodies: (cb: (poses: Map<string, RigidBodyPose>) => void) => () => void;
    getLatestKeypointsRaw: () => KeypointsFrame | null;
    setOverlayVisibility: (charuco: boolean, skeleton: boolean) => void;
    trackerSchemas: Record<string, TrackedObjectDefinition>;
    activeTrackerId: string | null;
    getActiveSchema: () => TrackedObjectDefinition | null;
}

export const ServerContext = createContext<ServerContextValue | null>(null);

export const useServer = (): ServerContextValue => {
    const context = useContext(ServerContext);
    if (!context) throw new Error('useServer must be used within ServerContextProvider');
    return context;
};

/** Returns null when called outside ServerContextProvider (e.g. in a Web Worker). */
export const useServerOptional = (): ServerContextValue | null => {
    return useContext(ServerContext);
};
