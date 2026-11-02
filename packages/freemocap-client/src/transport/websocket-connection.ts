let clientId: string | undefined;

/** A random version 4 UUID. `crypto.randomUUID` exists only in secure contexts (HTTPS or
 *  localhost); a page served over plain HTTP from another computer still has getRandomValues. */
export function randomId(): string {
    if (typeof crypto.randomUUID === 'function') return crypto.randomUUID();
    const bytes = crypto.getRandomValues(new Uint8Array(16));
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    const hex = Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('');
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

export interface WebSocketConfig {
    url: string;
    reconnectDelay?: number;
    heartbeatInterval?: number;
    socketFactory?: (url: URL) => WebSocket;
}

export enum ConnectionState {
    DISCONNECTED = 'DISCONNECTED',
    CONNECTING = 'CONNECTING',
    CONNECTED = 'CONNECTED',
    RECONNECTING = 'RECONNECTING',
    FAILED = 'FAILED'
}

type EventCallback = (...args: any[]) => void;

export class WebSocketConnection {
    private ws: WebSocket | null = null;
    private config: Required<Omit<WebSocketConfig, "socketFactory">> & Pick<WebSocketConfig, "socketFactory">;
    private reconnectTimer: ReturnType<typeof setTimeout> | number | null = null;
    private heartbeatTimer: ReturnType<typeof setInterval> | number | null = null;
    private state: ConnectionState = ConnectionState.DISCONNECTED;
    /** Set by disconnect() — the only close that must NOT trigger reconnection. */
    private disconnectRequested: boolean = false;

    // Simple event emitter implementation for browser
    private listeners: Map<string, Set<EventCallback>> = new Map();

    constructor(config: WebSocketConfig) {
        this.config = {
            reconnectDelay: config.reconnectDelay ?? 5000,
            heartbeatInterval: config.heartbeatInterval ?? 30000,
            url: config.url,
            socketFactory: config.socketFactory
        };
    }

    // Simple event emitter methods
    public on(event: string, callback: EventCallback): void {
        if (!this.listeners.has(event)) {
            this.listeners.set(event, new Set());
        }
        this.listeners.get(event)!.add(callback);
    }

    public off(event: string, callback: EventCallback): void {
        this.listeners.get(event)?.delete(callback);
    }

    private emit(event: string, ...args: any[]): void {
        this.listeners.get(event)?.forEach(callback => {
            try {
                callback(...args);
            } catch {
                // A subscriber must not interrupt connection recovery or log every retry.
            }
        });
    }

    public connect(): void {
        if (this.state === ConnectionState.CONNECTING || this.state === ConnectionState.CONNECTED || this.state === ConnectionState.RECONNECTING) {
            return;
        }
        this.clearTimers();
        this.disconnectRequested = false;

        this.setState(ConnectionState.CONNECTING);

        try {
            const url = new URL(this.config.url);
            url.searchParams.set('client_id', clientId ??= randomId());
            url.searchParams.set('connection_id', randomId());
            const socket = this.config.socketFactory ? this.config.socketFactory(url) : new WebSocket(url);
            this.ws = socket;
            socket.binaryType = 'arraybuffer';
            socket.onopen = () => { if (this.ws === socket) this.handleOpen(); };
            socket.onclose = (event) => { if (this.ws === socket) this.handleClose(event); };
            socket.onerror = (event) => { if (this.ws === socket) this.handleError(event); };
            socket.onmessage = (event) => { if (this.ws === socket) this.handleMessage(event); };
        } catch (error) {
            // Report why no socket could be made (a bad URL, say) instead of retrying silently.
            this.emit('error', error);
            this.scheduleReconnect();
        }
    }

    public disconnect(): void {
        this.clearTimers();
        this.disconnectRequested = true;

        if (this.ws) {
            const socket = this.ws;
            this.ws = null;
            socket.onopen = null;
            socket.onclose = null;
            socket.onerror = null;
            socket.onmessage = null;
            socket.close();
        }

        this.setState(ConnectionState.DISCONNECTED);
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
            this.emit('send-error', error);
            return false;
        }
    }

    public isConnected(): boolean {
        return this.ws?.readyState === 1;
    }

    public updateUrl(url: string): void {
        this.config.url = url;
    }

    public getState(): ConnectionState {
        return this.state;
    }

    private setState(state: ConnectionState): void {
        const previousState = this.state;
        this.state = state;
        this.emit('state-change', state, previousState);
    }

    private handleOpen(): void {
        this.setState(ConnectionState.CONNECTED);
        this.startHeartbeat();
        this.emit('open');
    }

    private handleClose(event: CloseEvent): void {
        this.clearTimers();

        this.ws = null;
        if (!this.disconnectRequested) {
            this.scheduleReconnect();
        } else {
            this.setState(ConnectionState.DISCONNECTED);
        }

        this.emit('close', event);
    }

    private handleError(error: Event): void {
        this.emit('error', error);
    }

    private handleMessage(event: MessageEvent): void {
        this.emit('message', event);
    }

    /** Retry quietly until the caller explicitly disconnects, even after server errors. */
    private scheduleReconnect(): void {
        if (this.reconnectTimer) return;

        this.setState(ConnectionState.RECONNECTING);
        this.reconnectTimer = (typeof window === "undefined" ? globalThis : window).setTimeout(() => {
            this.reconnectTimer = null;
            this.setState(ConnectionState.DISCONNECTED);
            this.connect();
        }, this.config.reconnectDelay);
    }

    private startHeartbeat(): void {
        this.heartbeatTimer = (typeof window === "undefined" ? globalThis : window).setInterval(() => {
            if (this.isConnected()) {
                this.sendRaw('ping');
            }
        }, this.config.heartbeatInterval);
    }

    /**
     * Send a raw text string over the WebSocket without JSON serialization.
     * Used for protocol-level messages like ping/pong.
     */
    public sendRaw(text: string): boolean {
        if (!this.isConnected()) {
            return false;
        }
        try {
            this.ws!.send(text);
            return true;
        } catch {
            return false;
        }
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
