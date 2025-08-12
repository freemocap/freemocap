import React, {createContext, ReactNode, useContext} from "react";
import { useWebSocket} from "@/context/websocket-context/useWebSocket";
import {CameraImageData} from "@/context/websocket-context/useWebsocketBinaryMessageProcessor";
import * as THREE from "three";


interface WebSocketContextProps {
    isConnected: boolean;
    connect: () => void;
    disconnect: () => void;
    latestCameraData: Record<string, CameraImageData>;
    acknowledgeFrameRendered: (cameraId: string, frameNumber: number) => void;
}


interface WebSocketProviderProps {
    url: string;
    children: ReactNode;
}

const WebSocketContext = createContext<WebSocketContextProps | undefined>(undefined);

export const WebSocketContextProvider: React.FC<WebSocketProviderProps> = ({url, children}) => {
    const { isConnected, connect, disconnect, latestCameraData,acknowledgeFrameRendered } = useWebSocket(url);

    return (
        <WebSocketContext.Provider value={{isConnected, connect, disconnect,
            latestCameraData,acknowledgeFrameRendered}}>
            {children}
        </WebSocketContext.Provider>
    )
}

export const useWebSocketContext = () => {
    const context = useContext(WebSocketContext);
    if (!context) {
        throw new Error('useWebSocketContext must be used within a WebSocketProvider');
    }
    return context;
};
