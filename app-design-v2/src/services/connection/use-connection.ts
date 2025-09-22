// services/connection/use-connection.ts
import { useCallback, useEffect, useMemo } from 'react';
import { useAppSelector, useAppDispatch } from '@/store/hooks';
import {
    selectConnectionStatus,
    selectWebSocketStatus,
    selectConnectionError,
    selectServerConfig,
    selectConnectionMode,
    connectToServer,
    disconnectFromServer,
    updateServerConfig
} from '@/store';
import { websocketService } from '@/services/websocket/websocket-service';
import { connectionOrchestrator } from '@/services/connection/connection-orchestrator';

export interface ConnectionState {
    // Server connection
    serverStatus: 'disconnected' | 'connecting' | 'connected' | 'disconnecting' | 'error';
    serverMode: 'none' | 'managed' | 'external';
    serverError: string | null;

    // WebSocket connection
    wsStatus: 'disconnected' | 'connecting' | 'connected' | 'reconnecting' | 'error';
    wsError: string | null;

    // Combined states
    isFullyConnected: boolean;
    isConnecting: boolean;
    canConnect: boolean;
    canDisconnect: boolean;
}

export interface ConnectionActions {
    // Server actions
    connectManaged: (executablePath?: string | null) => Promise<void>;
    connectExternal: (host?: string, port?: number) => Promise<void>;
    disconnect: () => Promise<void>;

    // WebSocket actions
    send: (data: string | object) => void;
    sendBinary: (data: ArrayBuffer) => void;

    // Configuration
    updateConfig: (config: Partial<{
        host: string;
        port: number;
        autoConnect: boolean;
        autoSpawn: boolean;
    }>) => void;
}

export function useConnection(): [ConnectionState, ConnectionActions] {
    const dispatch = useAppDispatch();

    // Selectors
    const serverStatus = useAppSelector(selectConnectionStatus);
    const serverMode = useAppSelector(selectConnectionMode);
    const serverError = useAppSelector(selectConnectionError);
    const wsStatus = useAppSelector(selectWebSocketStatus);
    const config = useAppSelector(selectServerConfig);

    // Memoized state
    const state = useMemo<ConnectionState>(() => ({
        serverStatus,
        serverMode,
        serverError,
        wsStatus,
        wsError: null, // WebSocket errors could be added to Redux if needed
        isFullyConnected: serverStatus === 'connected' && wsStatus === 'connected',
        isConnecting: serverStatus === 'connecting' || wsStatus === 'connecting',
        canConnect: serverStatus === 'disconnected' || serverStatus === 'error',
        canDisconnect: serverStatus === 'connected' || serverStatus === 'error',
    }), [serverStatus, serverMode, serverError, wsStatus]);

    // Actions
    const connectManaged = useCallback(async (executablePath?: string | null) => {
        await dispatch(connectToServer({
            mode: 'managed',
            executablePath
        })).unwrap();
    }, [dispatch]);

    const connectExternal = useCallback(async (host?: string, port?: number) => {
        await dispatch(connectToServer({
            mode: 'external',
            host,
            port
        })).unwrap();
    }, [dispatch]);

    const disconnect = useCallback(async () => {
        await dispatch(disconnectFromServer()).unwrap();
    }, [dispatch]);

    const send = useCallback((data: string | object) => {
        if (typeof data === 'string') {
            websocketService.send(data);
        } else {
            websocketService.sendMessage(data);
        }
    }, []);

    const sendBinary = useCallback((data: ArrayBuffer) => {
        websocketService.send(data);
    }, []);

    const updateConfig = useCallback((newConfig: Parameters<ConnectionActions['updateConfig']>[0]) => {
        dispatch(updateServerConfig(newConfig));

        // Update WebSocket service config if needed
        if (newConfig.autoConnect !== undefined) {
            websocketService.updateConfig({
                autoConnect: newConfig.autoConnect
            });
        }
    }, [dispatch]);

    // Auto-initialization
    useEffect(() => {
        websocketService.initialize();
    }, []);

    const actions = useMemo<ConnectionActions>(() => ({
        connectManaged,
        connectExternal,
        disconnect,
        send,
        sendBinary,
        updateConfig,
    }), [connectManaged, connectExternal, disconnect, send, sendBinary, updateConfig]);

    return [state, actions];
}

