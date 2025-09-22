// store/slices/server/server-types.ts

/**
 * Server connection status
 */
export type ServerStatus =
    | 'healthy' // Healthy check endpoint is reachable
    | 'disconnected' // Not connected (health check returns not found)
    | 'closing' // In the process of shutting down
    | 'error'; // Error state (e.g., health check or shutdown returns error)

/**
 * Server configuration (persisted to localStorage)
 */
export interface ServerConfig {
    host: string;
    port: number;
}

/**
 * Server connection information
 */
export interface ServerConnectionInfo {
    status: ServerStatus;
    serverUrl: string | null;
    error: string | null;
    lastHealthCheck: string | null;
    retryCount: number;
}

/**
 * Complete server state
 */
export interface ServerState {
    config: ServerConfig;
    connection: ServerConnectionInfo;
}

/**
 * Server connection options
 */
export interface ServerConnectionOptions {
    host?: string;
    port?: number;
}

export interface ExternalServerConnectionResult {
    serverUrl: string;
    isHealthy: boolean;
}
