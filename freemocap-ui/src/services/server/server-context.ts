import { createContext, useContext } from 'react';
import type { FramerateStore } from './server-helpers/framerate-store';
import type { LogStore } from './server-helpers/log-store';
import type { KeypointsCallback, KeypointsFrame, ModelFramesCallback, ModelsCallback } from '@/components/viewport3d/KeypointsSourceContext';
import type { ResolvedModelFrame } from './transport/frame-types';
import type { ModelDefinition } from './transport/message-contract';

export interface ServerContextValue {
    isConnected: boolean;
    isFailed: boolean;
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
    subscribeToKeypoints: (cb: KeypointsCallback) => () => void;
    getLatestKeypoints: () => KeypointsFrame | null;
    setOverlayVisibility: (charuco: boolean, skeleton: boolean) => void;
    /** The static model definitions, emitted only when the model set changes. */
    subscribeToModels: (cb: ModelsCallback) => () => void;
    getModels: () => ModelDefinition[] | null;
    /** Every tracked model's per-frame numbers — origins, landmarks, rotations, fitted
     *  lengths and derived points, one entry per tracked thing. */
    subscribeToModelFrames: (cb: ModelFramesCallback) => () => void;
    getLatestModelFrames: () => ResolvedModelFrame[] | null;
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
