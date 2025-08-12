import React, {createContext, ReactNode, useContext} from "react";
import {useWebSocket} from "@/hooks/useWebSocket";
import {z} from "zod";
import {FrontendFramePayloadSchema, JpegImagesSchema, Points3dSchema} from "@/models/FrontendFramePayloadSchema";
import {SkellyCamAppStateSchema} from "@/models/SkellyCamAppStateSchema";

interface WebSocketContextProps {
    isConnected: boolean;
    latestFrontendPayload: z.infer<typeof FrontendFramePayloadSchema> | null;
    latestSkellyCamAppState: z.infer<typeof SkellyCamAppStateSchema> | null;
    latestImages:z.infer<typeof JpegImagesSchema> |null;
    latestPoints3d: z.infer<typeof Points3dSchema> | null;
    connect: () => void;
    disconnect: () => void;
}

interface WebSocketProviderProps {
    url: string;
    children: ReactNode;
}

const WebSocketContext = createContext<WebSocketContextProps | undefined>(undefined);

export const WebSocketProvider: React.FC<WebSocketProviderProps> = ({url, children}) => {
    const {isConnected, latestFrontendPayload,  latestImages, latestPoints3d, latestSkellyCamAppState, connect, disconnect} = useWebSocket(url);

    return (
        <WebSocketContext.Provider value={{isConnected, latestFrontendPayload,latestImages, latestPoints3d, latestSkellyCamAppState, connect, disconnect}}>
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
