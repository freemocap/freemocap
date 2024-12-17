import React, {createContext, useContext, ReactNode} from "react";
import {useWebSocket} from "@/hooks/useWebSocket";

interface WebSocketContextProps {
    isConnected: boolean;
    messages: string[];
    connect: () => void;
    disconnect: () => void;
}
interface WebSocketProviderProps {
    url: string;
    children: ReactNode;
}
const WebSocketContext = createContext<WebSocketContextProps | undefined>(undefined);

export const WebSocketProvider: React.FC<WebSocketProviderProps> = ({url, children}) => {
    const {isConnected, messages, connect, disconnect} = useWebSocket(url);

    return(
        <WebSocketContext.Provider value={{isConnected, messages, connect, disconnect}}>
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
