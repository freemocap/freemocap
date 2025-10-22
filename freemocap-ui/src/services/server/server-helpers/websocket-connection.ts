export interface WebSocketConfig {
    url: string;
    reconnectDelay?: number;
    maxReconnectAttempts?: number;
    heartbeatInterval?: number;
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
    private config: Required<WebSocketConfig>;
    private reconnectAttempts: number = 0;
    private reconnectTimer: number | null = null;
    private heartbeatTimer: number | null = null;
    private state: ConnectionState = ConnectionState.DISCONNECTED;

    // Simple event emitter implementation for browser
    private listeners: Map<string, Set<EventCallback>> = new Map();

    constructor(config: WebSocketConfig) {
        this.config = {
            reconnectDelay: config.reconnectDelay ?? 1000,
            maxReconnectAttempts: config.maxReconnectAttempts ?? 5,
            heartbeatInterval: config.heartbeatInterval ?? 30000,
            url: config.url
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
            } catch (error) {
                console.error(`Error in event listener for ${event}:`, error);
            }
        });
    }

    public connect(): void {
        if (this.state === ConnectionState.CONNECTING || this.state === ConnectionState.CONNECTED) {
            return;
        }

        this.setState(ConnectionState.CONNECTING);

        try {
            console.log(`Connecting to WebSocket at ${this.config.url}`);
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

    public disconnect(): void {
        this.clearTimers();
        this.reconnectAttempts = 0;

        if (this.ws) {
            // Remove handlers to avoid reconnection on close
            this.ws.onclose = null;
            this.ws.close();
            this.ws = null;
        }

        this.setState(ConnectionState.DISCONNECTED);
    }

    public send(data: string | object): boolean {
        if (!this.isConnected()) {
            console.warn('WebSocket not connected, queuing message');
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

    private setState(state: ConnectionState): void {
        const previousState = this.state;
        this.state = state;
        this.emit('state-change', state, previousState);
    }

    private handleOpen(): void {
        console.log('WebSocket connected');
        this.reconnectAttempts = 0;
        this.setState(ConnectionState.CONNECTED);
        this.startHeartbeat();
        this.emit('open');
    }

    private handleClose(event: CloseEvent): void {
        console.log(`WebSocket closed: code=${event.code}, reason=${event.reason}`);
        this.clearTimers();

        const wasConnected = this.state === ConnectionState.CONNECTED;

        if (wasConnected && this.reconnectAttempts < this.config.maxReconnectAttempts) {
            this.scheduleReconnect();
        } else if (this.reconnectAttempts >= this.config.maxReconnectAttempts) {
            this.setState(ConnectionState.FAILED);
            this.emit('max-reconnect-attempts');
        } else {
            this.setState(ConnectionState.DISCONNECTED);
        }

        this.emit('close', event);
    }

    private handleError(error: Event): void {
        console.error('WebSocket error:', error);
        this.emit('error', error);
    }

    private handleMessage(event: MessageEvent): void {
        this.emit('message', event);
    }

    private scheduleReconnect(): void {
        if (this.reconnectTimer) return;

        this.setState(ConnectionState.RECONNECTING);
        const delay = Math.min(
            this.config.reconnectDelay * Math.pow(2, this.reconnectAttempts),
            10000 // Max 10 seconds
        );

        console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts + 1}/${this.config.maxReconnectAttempts})`);

        this.reconnectTimer = window.setTimeout(() => {
            this.reconnectTimer = null;
            this.reconnectAttempts++;
            this.connect();
        }, delay);
    }

    private startHeartbeat(): void {
        this.heartbeatTimer = window.setInterval(() => {
            if (this.isConnected()) {
                this.send({type: 'ping'});
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
