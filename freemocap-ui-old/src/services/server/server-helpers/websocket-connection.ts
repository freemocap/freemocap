export interface WebSocketConfig {
    url: string;
    reconnectDelay?: number;
    maxReconnectAttempts?: number;
    heartbeatInterval?: number;
    /** When true, silently poll for the server and auto-connect when it appears. */
    autoConnect?: boolean;
    /** Polling interval (ms) when in auto-connect discovery mode. */
    autoConnectInterval?: number;
}

export enum ConnectionState {
    /** Idle — not trying to connect. */
    DISCONNECTED = 'DISCONNECTED',
    /** Actively opening a WebSocket connection. */
    CONNECTING = 'CONNECTING',
    /** WebSocket is open. */
    CONNECTED = 'CONNECTED',
    /** Lost connection, attempting to re-establish. */
    RECONNECTING = 'RECONNECTING',
    /** Silently polling for the server to become available. */
    DISCOVERING = 'DISCOVERING',
}

/** Typed event map — each key declares its callback signature. */
interface WebSocketEventMap {
    'state-change': (newState: ConnectionState, previousState: ConnectionState) => void;
    'message': (event: MessageEvent) => void;
    'open': () => void;
    'close': (event: CloseEvent) => void;
    'error': (event: Event) => void;
    'send-failed': (data: string | object) => void;
    'send-error': (error: unknown) => void;
    'max-reconnect-attempts': () => void;
}

type EventName = keyof WebSocketEventMap;

export class WebSocketConnection {
    private ws: WebSocket | null = null;
    private config: Required<WebSocketConfig>;
    private reconnectAttempts: number = 0;
    private reconnectTimer: number | null = null;
    private heartbeatTimer: number | null = null;
    private discoveryTimer: number | null = null;
    private state: ConnectionState = ConnectionState.DISCONNECTED;

    private listeners: { [K in EventName]?: Set<WebSocketEventMap[K]> } = {};

    constructor(config: WebSocketConfig) {
        this.config = {
            reconnectDelay: config.reconnectDelay ?? 1000,
            maxReconnectAttempts: config.maxReconnectAttempts ?? 5,
            heartbeatInterval: config.heartbeatInterval ?? 30000,
            autoConnect: config.autoConnect ?? false,
            autoConnectInterval: config.autoConnectInterval ?? 3000,
            url: config.url,
        };
    }

    public on<K extends EventName>(event: K, callback: WebSocketEventMap[K]): void {
        if (!this.listeners[event]) {
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            this.listeners[event] = new Set() as any;
        }
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (this.listeners[event] as any).add(callback);
    }

    public off<K extends EventName>(event: K, callback: WebSocketEventMap[K]): void {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (this.listeners[event] as any)?.delete(callback);
    }

    private emit<K extends EventName>(event: K, ...args: Parameters<WebSocketEventMap[K]>): void {
        const set = this.listeners[event];
        if (!set) return;
        for (const callback of set) {
            try {
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                (callback as any)(...args);
            } catch (error) {
                console.error(`Error in event listener for ${event}:`, error);
            }
        }
    }

    /**
     * Begin actively trying to open the WebSocket connection.
     * If autoConnect is enabled and the attempt fails, falls back to discovery mode.
     */
    public connect(): void {
        if (this.state === ConnectionState.CONNECTING || this.state === ConnectionState.CONNECTED) {
            return;
        }

        this.stopDiscovery();
        this.setState(ConnectionState.CONNECTING);

        try {
            this.ws = new WebSocket(this.config.url);
            this.ws.binaryType = 'arraybuffer';

            this.ws.onopen = this.handleOpen.bind(this);
            this.ws.onclose = this.handleClose.bind(this);
            this.ws.onerror = this.handleError.bind(this);
            this.ws.onmessage = this.handleMessage.bind(this);
        } catch (error) {
            this.handleError(error as Event);
        }
    }

    /**
     * Cleanly close the connection and stop all reconnection/discovery.
     */
    public disconnect(): void {
        this.clearTimers();
        this.stopDiscovery();
        this.reconnectAttempts = 0;

        if (this.ws) {
            this.ws.onclose = null;
            this.ws.close();
            this.ws = null;
        }

        this.setState(ConnectionState.DISCONNECTED);
    }

    /**
     * Enter discovery mode: silently poll for the server at a fixed interval.
     * Does not surface errors — just keeps trying until the server appears.
     */
    public startDiscovery(): void {
        if (this.state === ConnectionState.CONNECTED || this.state === ConnectionState.CONNECTING) {
            return;
        }

        console.log(`[WS] Entering discovery mode (polling every ${this.config.autoConnectInterval}ms)`);
        this.setState(ConnectionState.DISCOVERING);
        this.scheduleDiscoveryAttempt();
    }

    public send(data: string | object): boolean {
        if (!this.isConnected()) {
            this.emit('send-failed', data);
            return false;
        }

        try {
            const payload = typeof data === 'string' ? data : JSON.stringify(data);
            this.ws!.send(payload);
            return true;
        } catch (error) {
            console.error('Failed to send WebSocket message:', error);
            this.emit('send-error', error);
            return false;
        }
    }

    public isConnected(): boolean {
        return this.ws?.readyState === WebSocket.OPEN;
    }

    public getState(): ConnectionState {
        return this.state;
    }

    // -----------------------------------------------------------
    // Private
    // -----------------------------------------------------------

    private setState(state: ConnectionState): void {
        const previousState = this.state;
        this.state = state;
        this.emit('state-change', state, previousState);
    }

    private handleOpen(): void {
        console.log('WebSocket connected');
        this.reconnectAttempts = 0;
        this.stopDiscovery();
        this.setState(ConnectionState.CONNECTED);
        this.startHeartbeat();
        this.emit('open');
    }

    private handleClose(event: CloseEvent): void {
        console.log(`WebSocket closed: code=${event.code}, reason=${event.reason}`);
        this.clearTimers();
        this.ws = null;

        // Always transition to DISCONNECTED first — this triggers cleanup
        // in listeners (e.g. ServerContextProvider dispatches serverSettingsCleared)
        this.setState(ConnectionState.DISCONNECTED);
        this.emit('close', event);

        // If autoConnect is on, immediately start polling for the server again
        if (this.config.autoConnect) {
            this.startDiscovery();
            return;
        }

        if (this.reconnectAttempts < this.config.maxReconnectAttempts) {
            this.scheduleReconnect();
        } else {
            this.emit('max-reconnect-attempts');
        }
    }

    private handleError(_error: Event): void {
        // In discovery mode, errors are expected and silenced
        if (this.state === ConnectionState.DISCOVERING) {
            return;
        }
        this.emit('error', _error);
    }

    private handleMessage(event: MessageEvent): void {
        this.emit('message', event);
    }

    private scheduleReconnect(): void {
        if (this.reconnectTimer) return;

        this.setState(ConnectionState.RECONNECTING);
        const delay = Math.min(
            this.config.reconnectDelay * Math.pow(2, this.reconnectAttempts),
            10000,
        );

        console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts + 1}/${this.config.maxReconnectAttempts})`);

        this.reconnectTimer = window.setTimeout(() => {
            this.reconnectTimer = null;
            this.reconnectAttempts++;
            this.connect();
        }, delay);
    }

    /**
     * Schedule one discovery probe. On failure, schedule the next one.
     * On success, handleOpen() takes over.
     */
    private scheduleDiscoveryAttempt(): void {
        if (this.discoveryTimer !== null) return;

        this.discoveryTimer = window.setTimeout(() => {
            this.discoveryTimer = null;

            if (this.state !== ConnectionState.DISCOVERING) return;

            try {
                const probe = new WebSocket(this.config.url);
                probe.binaryType = 'arraybuffer';

                probe.onopen = () => {
                    console.log('[WS] Discovery probe succeeded — promoting to main connection');
                    // Discovery succeeded — promote this socket to the main connection
                    this.ws = probe;
                    probe.onclose = this.handleClose.bind(this);
                    probe.onerror = this.handleError.bind(this);
                    probe.onmessage = this.handleMessage.bind(this);
                    this.handleOpen();
                };

                probe.onerror = () => {
                    // Silently swallow — try again on the next interval
                    try { probe.close(); } catch { /* ignore */ }
                    if (this.state === ConnectionState.DISCOVERING) {
                        this.scheduleDiscoveryAttempt();
                    }
                };

                probe.onclose = () => {
                    // If we get a close without ever opening, try again
                    if (this.state === ConnectionState.DISCOVERING) {
                        this.scheduleDiscoveryAttempt();
                    }
                };
            } catch {
                // WebSocket constructor threw — try again
                if (this.state === ConnectionState.DISCOVERING) {
                    this.scheduleDiscoveryAttempt();
                }
            }
        }, this.config.autoConnectInterval);
    }

    private stopDiscovery(): void {
        if (this.discoveryTimer !== null) {
            clearTimeout(this.discoveryTimer);
            this.discoveryTimer = null;
        }
    }

    private startHeartbeat(): void {
        this.heartbeatTimer = window.setInterval(() => {
            if (this.isConnected()) {
                // Send plain text "ping" — the backend expects this format
                this.ws!.send('ping');
            }
        }, this.config.heartbeatInterval);
    }

    private clearTimers(): void {
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
        if (this.heartbeatTimer) {
            clearInterval(this.heartbeatTimer);
            this.heartbeatTimer = null;
        }
    }
}
