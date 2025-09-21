// store/slices/server/server-types.ts

/**
 * Server connection modes:
 * - 'none': Not connected to any server
 * - 'managed': Connected to a server spawned by this app
 * - 'external': Connected to an external server (not spawned by this app)
 */
export type ServerConnectionMode = 'none' | 'managed' | 'external';

/**
 * Server connection status
 */
export type ServerStatus =
    | 'disconnected'
    | 'connecting'
    | 'connected'
    | 'disconnecting'
    | 'error';

/**
 * WebSocket connection status
 */
export type WebSocketStatus =
    | 'disconnected'
    | 'connecting'
    | 'connected'
    | 'reconnecting'
    | 'error';

/**
 * Server configuration (persisted to localStorage)
 */
export interface ServerConfig {
    host: string;
    port: number;
    autoConnect: boolean;      // Auto-connect WebSocket when server is available
    autoSpawn: boolean;        // Auto-spawn server on app start (Electron only)
    preferredExecutablePath: string | null;  // Preferred executable for spawning
}

/**
 * Information about a managed process
 */
export interface ManagedProcess {
    pid: number | null;
    executablePath: string | null;
}

/**
 * Server connection information
 */
export interface ServerConnectionInfo {
    mode: ServerConnectionMode;
    status: ServerStatus;
    managedProcess: ManagedProcess | null;  // Only set when mode is 'managed'
    serverUrl: string | null;
    error: string | null;
    lastHealthCheck: string | null;
    retryCount: number;
}

/**
 * WebSocket connection state
 */
export interface WebSocketState {
    status: WebSocketStatus;
    error: string | null;
    reconnectAttempts: number;
    lastConnectedAt: string | null;
    lastDisconnectedAt: string | null;
}

/**
 * Executable candidate information
 */
export interface ExecutableCandidate {
    name: string;
    path: string;
    description: string;
    isValid: boolean;
    error?: string;
    resolvedPath?: string;
}

/**
 * Executable management state
 */
export interface ExecutableState {
    candidates: ExecutableCandidate[];
    lastRefresh: string | null;
    isRefreshing: boolean;
}

/**
 * Complete server state
 */
export interface ServerState {
    config: ServerConfig;
    connection: ServerConnectionInfo;
    websocket: WebSocketState;
    executables: ExecutableState;
}

/**
 * Server connection options
 */
export interface ServerConnectionOptions {
    host?: string;
    port?: number;
    executablePath?: string | null;
}

/**
 * Server startup result
 */
export interface ServerStartupResult {
    process: ManagedProcess;
    serverUrl: string;
}

/**
 * External server connection result
 */
export interface ExternalServerConnectionResult {
    serverUrl: string;
    isHealthy: boolean;
}
