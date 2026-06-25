import React, {ReactNode, useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {ConnectionState, WebSocketConnection} from '@/services/server/server-helpers/websocket-connection';
import {PipelineTimingStore} from '@/services/server/server-helpers/pipeline-timing-store';
import {serverUrls} from '@/services';
import {DEFAULT_HOST, DEFAULT_PORT} from '@/constants/server-urls';
import {STORAGE_KEYS, loadFromStorage} from '@/components/control-panels/server-connection/storage';
import {
    isFramerateUpdate,
    isPipelineTiming,
} from '@/services/server/server-helpers/websocket-message-types';
import {
    MetricsServerContext,
    type MetricsServerContextValue,
} from '@/services/server/metrics-server-context';

export {useMetricsServer, MetricsServerContext} from '@/services/server/metrics-server-context';

export const MetricsServerContextProvider: React.FC<{children: ReactNode}> = ({children}) => {
    const [isConnected, setIsConnected] = useState(false);
    const wsConnectionRef = useRef<WebSocketConnection | null>(null);
    const pipelineTimingStoreRef = useRef<PipelineTimingStore>(new PipelineTimingStore());

    useEffect(() => {
        const host = loadFromStorage(STORAGE_KEYS.SERVER_HOST, DEFAULT_HOST);
        const port = loadFromStorage(STORAGE_KEYS.SERVER_PORT, DEFAULT_PORT);
        serverUrls.setHost(host);
        serverUrls.setPort(port);

        wsConnectionRef.current = new WebSocketConnection({
            url: serverUrls.getWebSocketUrl('metrics'),
            reconnectDelay: 1000,
            maxReconnectAttempts: 10,
            heartbeatInterval: 30000,
        });

        return () => {
            wsConnectionRef.current?.disconnect();
        };
    }, []);

    useEffect(() => {
        const ws = wsConnectionRef.current;
        if (!ws) return;

        const handleStateChange = (newState: ConnectionState): void => {
            setIsConnected(newState === ConnectionState.CONNECTED);
            if (newState === ConnectionState.DISCONNECTED || newState === ConnectionState.FAILED) {
                pipelineTimingStoreRef.current.clear();
            }
        };

        const handleMessage = (event: MessageEvent): void => {
            if (event.data instanceof ArrayBuffer) {
                return;
            }
            if (typeof event.data !== 'string' || event.data === 'pong') {
                return;
            }
            try {
                const jsonData = JSON.parse(event.data);
                if (isPipelineTiming(jsonData)) {
                    pipelineTimingStoreRef.current.ingestBackendMessage(jsonData);
                } else if (isFramerateUpdate(jsonData)) {
                    const mean = jsonData.backend_framerate.frame_duration_mean;
                    if (mean != null && mean > 0) {
                        pipelineTimingStoreRef.current.setBackendFrameDurationMs(mean);
                    }
                }
            } catch (error) {
                console.error('[metrics-ws] parse error:', error);
            }
        };

        ws.on('state-change', handleStateChange);
        ws.on('message', handleMessage);
        ws.connect();

        return () => {
            ws.off('state-change', handleStateChange);
            ws.off('message', handleMessage);
            ws.disconnect();
        };
    }, []);

    const connect = useCallback((): void => {
        wsConnectionRef.current?.connect();
    }, []);

    const disconnect = useCallback((): void => {
        wsConnectionRef.current?.disconnect();
    }, []);

    const getPipelineTimingStore = useCallback((): PipelineTimingStore => {
        return pipelineTimingStoreRef.current;
    }, []);

    const contextValue = useMemo((): MetricsServerContextValue => ({
        isConnected,
        connect,
        disconnect,
        getPipelineTimingStore,
    }), [isConnected, connect, disconnect, getPipelineTimingStore]);

    return (
        <MetricsServerContext.Provider value={contextValue}>
            {children}
        </MetricsServerContext.Provider>
    );
};
