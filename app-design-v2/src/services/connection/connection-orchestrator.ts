// services/connection/connection-orchestrator.ts
import { store } from '@/store';
import { websocketService } from '@/services/websocket/websocket-service';
import {
    connectionStatusChanged,
    connectionModeChanged,
    serverUrlUpdated,
    connectionErrorSet,
    websocketStatusChanged,
} from '@/store';
import type {ServerStatus} from "@/store/slices/connection/connection-types.ts";
import {selectServerConfig} from "@/store/slices/connection/connection-selectors.ts";

export interface ConnectionOptions {
    host?: string;
    port?: number;
    autoConnectWebSocket?: boolean;
}

export interface ConnectionResult {
    success: boolean;
    serverUrl?: string;
    error?: string;
    processInfo?: {
        pid: number;
        executablePath: string;
    };
}

class ConnectionOrchestrator {
    private static instance: ConnectionOrchestrator;
    private healthCheckTimer: NodeJS.Timeout | null = null;
    private connectionPromise: Promise<ConnectionResult> | null = null;
    private abortController: AbortController | null = null;

    private readonly HEALTH_CHECK_INTERVAL = 5000; // 5 seconds
    private readonly MAX_HEALTH_RETRIES = 10;
    private readonly HEALTH_RETRY_DELAY = 1000;

    private constructor() {}

    static getInstance(): ConnectionOrchestrator {
        if (!ConnectionOrchestrator.instance) {
            ConnectionOrchestrator.instance = new ConnectionOrchestrator();
        }
        return ConnectionOrchestrator.instance;
    }

    /**
     * Connect to server (managed or external)
     */
    async connect(options: ConnectionOptions): Promise<ConnectionResult> {
        // Prevent multiple simultaneous connection attempts
        if (this.connectionPromise) {
            console.log('Connection already in progress');
            return this.connectionPromise;
        }

        // Create abort controller for cancellation
        this.abortController = new AbortController();

        this.connectionPromise = this.performConnection(options);

        try {
            const result = await this.connectionPromise;

            // Auto-connect WebSocket if requested and server is up
            if (result.success && options.autoConnectWebSocket !== false) {
                await this.connectWebSocket();
            }

            return result;
        } finally {
            this.connectionPromise = null;
            this.abortController = null;
        }
    }

    /**
     * Disconnect from server
     */
    async disconnect(): Promise<void> {
        console.log('Disconnecting from server');

        // Cancel any ongoing connection
        if (this.abortController) {
            this.abortController.abort();
        }

        // Stop health checks
        this.stopHealthCheck();

        // Disconnect WebSocket
        websocketService.disconnect();

        // Update status
        store.dispatch(connectionStatusChanged('disconnecting'));

        try {
                // For external servers, just update state
                store.dispatch(connectionModeChanged('none'));
                store.dispatch(connectionStatusChanged('disconnected'));
                store.dispatch(serverUrlUpdated(null));
        } catch (error) {
            console.error('Error during disconnect:', error);
            throw error;
        }
    }

    /**
     * Check if server is healthy
     */
    async checkHealth(url: string, signal?: AbortSignal): Promise<boolean> {
        try {
            const response = await fetch(`${url}/health`, {
                signal: signal || AbortSignal.timeout(3000),
            });
            return response.ok;
        } catch (error) {
            if (error instanceof Error && error.name === 'AbortError') {
                console.log('Health check aborted');
            }
            return false;
        }
    }

    /**
     * Get server status
     */
    getStatus(): ServerStatus {
        const state = store.getState();
        return state.server.connection.status;
    }

    /**
     * Check if connected
     */
    isConnected(): boolean {
        return this.getStatus() === 'connected';
    }

    // Private methods

    private async performConnection(options: ConnectionOptions): Promise<ConnectionResult> {
        const {  host, port } = options;

        // Get config from store if not provided
        const state = store.getState();
        const config = selectServerConfig(state);
        const actualHost = host ?? config.host;
        const actualPort = port ?? config.port;
        const serverUrl = `http://${actualHost}:${actualPort}`;

        // Update connection state
        store.dispatch(connectionStatusChanged('connecting'));
        store.dispatch(connectionErrorSet(null));

        try {
            return await this.connectExternalServer(serverUrl);
        } catch (error) {
            const errorMsg = error instanceof Error ? error.message : 'Connection failed';
            console.error('Connection failed:', errorMsg);

            store.dispatch(connectionStatusChanged('error'));
            store.dispatch(connectionErrorSet(errorMsg));
            store.dispatch(connectionModeChanged('none'));

            return {
                success: false,
                error: errorMsg
            };
        }
    }

    private async connectExternalServer(serverUrl: string): Promise<ConnectionResult> {
        console.log(`Connecting to external server: ${serverUrl}`);

        // Check if server is healthy
        const isHealthy = await this.checkHealth(serverUrl, this.abortController?.signal);

        if (!isHealthy) {
            throw new Error(`No server responding at ${serverUrl}`);
        }

        // Update state
        store.dispatch(connectionStatusChanged('connected'));
        store.dispatch(serverUrlUpdated(serverUrl));

        // Start health monitoring
        this.startHealthCheck(serverUrl);

        return {
            success: true,
            serverUrl
        };
    }



    private async shutdownExistingServer(serverUrl: string): Promise<void> {
        try {
            await fetch(`${serverUrl}/shutdown`, {
                method: 'POST',
                signal: AbortSignal.timeout(1000)
            });
            // Wait a moment for shutdown
            await new Promise(resolve => setTimeout(resolve, 500));
        } catch {
            // Ignore shutdown errors - server might not be running
        }
    }

    private async waitForHealth(
        serverUrl: string
    ): Promise<boolean> {
        console.log(`Waiting for server health at ${serverUrl}`);

        for (let attempt = 1; attempt <= this.MAX_HEALTH_RETRIES; attempt++) {
            // Check if connection was aborted
            if (this.abortController?.signal.aborted) {
                console.log('Health check aborted');
                return false;
            }

            const isHealthy = await this.checkHealth(serverUrl, this.abortController?.signal);

            if (isHealthy) {
                console.log(`Server healthy after ${attempt} attempts`);
                return true;
            }

            if (attempt < this.MAX_HEALTH_RETRIES) {
                console.log(`Health check attempt ${attempt}/${this.MAX_HEALTH_RETRIES} failed, retrying...`);
                await new Promise(resolve => setTimeout(resolve, this.HEALTH_RETRY_DELAY));
            }
        }

        console.error(`Server failed to become healthy after ${this.MAX_HEALTH_RETRIES} attempts`);
        return false;
    }


    private async connectWebSocket(): Promise<void> {
        console.log('Auto-connecting WebSocket');
        store.dispatch(websocketStatusChanged('connecting'));
        websocketService.connect();
    }

    private startHealthCheck(serverUrl: string): void {
        this.stopHealthCheck();

        this.healthCheckTimer = setInterval(async () => {
            const isHealthy = await this.checkHealth(serverUrl);

            if (!isHealthy && this.isConnected()) {
                console.error('Server health check failed');
                store.dispatch(connectionStatusChanged('error'));
                store.dispatch(connectionErrorSet('Server health check failed'));
                this.stopHealthCheck();
            }
        }, this.HEALTH_CHECK_INTERVAL);
    }

    private stopHealthCheck(): void {
        if (this.healthCheckTimer) {
            clearInterval(this.healthCheckTimer);
            this.healthCheckTimer = null;
        }
    }
}

export const connectionOrchestrator = ConnectionOrchestrator.getInstance();
