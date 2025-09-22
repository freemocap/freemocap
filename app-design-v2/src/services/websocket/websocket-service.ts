// services/websocket/websocket-service.ts
import { store } from '@/store';
import {
    websocketConnected,
    websocketDisconnected,
    websocketError,
    websocketReconnecting,
    backendFramerateUpdated,
    frontendFramerateUpdated,
    logAdded,
    selectServerConfig,
    selectIsServerAlive,
    type LogRecord
} from '@/store';
import { frameRouter } from '../frames/frame-router.ts';
import type {
    WebSocketMessage,
    FramerateUpdateMessage,
    LogRecordMessage
} from './websocket-types.ts';

export type MessageHandler = (data: WebSocketMessage) => void;
export type BinaryHandler = (data: ArrayBuffer) => void;

interface WebSocketConfig {
    reconnect: boolean;
    reconnectInterval: number;
    maxReconnectAttempts: number;
    autoConnect: boolean;
    healthCheckInterval: number;
}

class WebSocketService {
    private static instance: WebSocketService;
    private ws: WebSocket | null = null;
    private messageHandlers = new Set<MessageHandler>();
    private binaryHandlers = new Set<BinaryHandler>();
    private reconnectTimer: NodeJS.Timeout | null = null;
    private healthCheckTimer: NodeJS.Timeout | null = null;
    private reconnectAttempts: number = 0;
    private intentionalDisconnect: boolean = false;
    private config: WebSocketConfig = {
        reconnect: true,
        reconnectInterval: 1000,
        maxReconnectAttempts: 10,
        autoConnect: true,
        healthCheckInterval: 30000,
    };
    private url: string | null = null;
    private isInitialized: boolean = false;
    private unsubscribe: (() => void) | null = null;

    // Debug stats
    private debugStats = {
        totalBinaryMessages: 0,
        totalTextMessages: 0,
        totalBytesReceived: 0,
        lastMessageTime: 0,
        messagesSinceConnect: 0,
    };

    private constructor() {
        console.log('🔧 WebSocketService: Constructor called');
    }

    static getInstance(): WebSocketService {
        if (!WebSocketService.instance) {
            console.log('🔧 WebSocketService: Creating new instance');
            WebSocketService.instance = new WebSocketService();
        }
        return WebSocketService.instance;
    }

    initialize(): void {
        if (this.isInitialized) {
            console.log('⚠️ WebSocketService: Already initialized');
            return;
        }

        console.log('🚀 WebSocketService: Initializing...');
        console.log('🚀 WebSocketService: Binary handlers count:', this.binaryHandlers.size);

        // Initialize frame router
        frameRouter.initialize();

        // Setup auto-connect monitoring
        this.setupAutoConnect();

        this.isInitialized = true;
        console.log('✅ WebSocketService: Initialization complete');
        console.log('🔧 WebSocketService: Config:', this.config);
    }

    connect(url?: string): void {
        console.log('🔌 WebSocketService: Connect called');

        if (this.ws?.readyState === WebSocket.OPEN) {
            console.log('⚠️ WebSocketService: Already connected');
            return;
        }

        // Reset flags when explicitly connecting
        this.intentionalDisconnect = false;
        this.config.reconnect = true;
        this.reconnectAttempts = 0;
        this.debugStats.messagesSinceConnect = 0;

        // Build URL if not provided
        if (!url) {
            const state = store.getState();
            const config = selectServerConfig(state);
            url = `ws://${config.host}:${config.port}/skellycam/websocket/connect`;
        }

        this.url = url;
        this.cleanup();

        try {
            console.log(`🔌 WebSocketService: Connecting to WebSocket: ${url}`);
            this.ws = new WebSocket(url);
            this.ws.binaryType = 'arraybuffer';
            console.log('🔧 WebSocketService: WebSocket created, binaryType:', this.ws.binaryType);
            this.setupEventHandlers();
        } catch (error) {
            const errorMsg = error instanceof Error ? error.message : 'Connection failed';
            console.error('❌ WebSocketService: Connection error:', errorMsg);
            store.dispatch(websocketError(errorMsg));
        }
    }

    disconnect(): void {
        console.log('🔌 WebSocketService: Disconnect called');
        this.intentionalDisconnect = true;
        this.config.reconnect = false;
        this.cleanup();
        store.dispatch(websocketDisconnected());

        // Log final stats
        console.log('📊 WebSocketService: Final stats:', this.debugStats);
    }

    send(data: string | ArrayBuffer): void {
        if (this.ws?.readyState === WebSocket.OPEN) {
            const dataType = typeof data === 'string' ? 'text' : 'binary';
            const dataSize = typeof data === 'string' ? data.length : data.byteLength;
            console.log(`📤 WebSocketService: Sending ${dataType} data, size: ${dataSize}`);
            this.ws.send(data);
        } else {
            console.warn('⚠️ WebSocketService: Cannot send - WebSocket not connected');
        }
    }

    sendMessage(message: object): void {
        console.log('📤 WebSocketService: Sending JSON message:', message);
        this.send(JSON.stringify(message));
    }

    acknowledgeFrameRendered(cameraId: string, frameNumber: number): void {
        console.log(`📤 WebSocketService: Acknowledging frame ${frameNumber} for camera ${cameraId}`);
        this.sendMessage({
            type: 'frame_ack',
            camera_id: cameraId,
            frame_number: frameNumber,
        });
    }

    addMessageHandler(handler: MessageHandler): () => void {
        console.log('➕ WebSocketService: Adding message handler');
        this.messageHandlers.add(handler);
        console.log('🔧 WebSocketService: Total message handlers:', this.messageHandlers.size);
        return () => {
            this.messageHandlers.delete(handler);
            console.log('➖ WebSocketService: Removed message handler, remaining:', this.messageHandlers.size);
        };
    }

    addBinaryHandler(handler: BinaryHandler): () => void {
        console.log('➕ WebSocketService: Adding binary handler');
        this.binaryHandlers.add(handler);
        console.log('🔧 WebSocketService: Total binary handlers:', this.binaryHandlers.size);
        return () => {
            this.binaryHandlers.delete(handler);
            console.log('➖ WebSocketService: Removed binary handler, remaining:', this.binaryHandlers.size);
        };
    }

    get isConnected(): boolean {
        return this.ws?.readyState === WebSocket.OPEN;
    }

    updateConfig(config: Partial<WebSocketConfig>): void {
        console.log('🔧 WebSocketService: Updating config:', config);
        this.config = { ...this.config, ...config };

        if (config.autoConnect !== undefined) {
            if (config.autoConnect) {
                this.setupAutoConnect();
            } else {
                this.teardownAutoConnect();
            }
        }
    }

    destroy(): void {
        console.log('💥 WebSocketService: Destroying service');
        this.disconnect();
        this.teardownAutoConnect();
        this.messageHandlers.clear();
        this.binaryHandlers.clear();
        this.isInitialized = false;
    }

    // Private methods

    private cleanup(): void {
        console.log('🧹 WebSocketService: Cleanup called');

        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }

        if (this.healthCheckTimer) {
            clearInterval(this.healthCheckTimer);
            this.healthCheckTimer = null;
        }

        if (this.ws) {
            console.log('🧹 WebSocketService: Closing WebSocket, current state:', this.ws.readyState);
            // Remove event handlers before closing
            this.ws.onopen = null;
            this.ws.onclose = null;
            this.ws.onerror = null;
            this.ws.onmessage = null;

            if (this.ws.readyState === WebSocket.OPEN) {
                this.ws.close();
            }
            this.ws = null;
        }
    }

    private setupEventHandlers(): void {
        if (!this.ws) {
            console.error('❌ WebSocketService: Cannot setup handlers - no WebSocket');
            return;
        }

        console.log('🔧 WebSocketService: Setting up event handlers');

        this.ws.onopen = () => {
            console.log('✅ WebSocketService: WebSocket connected');
            console.log('🔧 WebSocketService: ReadyState:', this.ws?.readyState);
            console.log('🔧 WebSocketService: Binary handlers available:', this.binaryHandlers.size);

            this.reconnectAttempts = 0;
            store.dispatch(websocketConnected());

            // Send hello message
            this.sendMessage({
                type: 'hello',
                message: 'Skellycam Frontend Connected'
            });

            // Start health check
            this.startHealthCheck();
        };

        this.ws.onclose = (event) => {
            console.log('🔌 WebSocketService: WebSocket disconnected');
            console.log('🔧 WebSocketService: Close event code:', event.code);
            console.log('🔧 WebSocketService: Close event reason:', event.reason);
            console.log('🔧 WebSocketService: Was clean close?:', event.wasClean);

            store.dispatch(websocketDisconnected());
            this.stopHealthCheck();

            // Only attempt reconnect if it wasn't an intentional disconnect
            if (!this.intentionalDisconnect) {
                console.log('🔄 WebSocketService: Will attempt reconnect');
                this.attemptReconnect();
            } else {
                console.log('✋ WebSocketService: Intentional disconnect, not reconnecting');
            }
        };

        this.ws.onerror = (event) => {
            console.error('❌ WebSocketService: WebSocket error:', event);
            store.dispatch(websocketError('WebSocket error occurred'));
        };

        this.ws.onmessage = (event) => {
            this.debugStats.messagesSinceConnect++;
            this.debugStats.lastMessageTime = Date.now();

            const dataSize = event.data instanceof ArrayBuffer ? event.data.byteLength : event.data.length;

            if (event.data instanceof ArrayBuffer) {
                this.debugStats.totalBinaryMessages++;
                this.debugStats.totalBytesReceived += dataSize;

                // Log every 10th binary message to avoid spam
                if (this.debugStats.totalBinaryMessages % 10 === 1) {
                    console.log(`📥 WebSocketService: Binary message #${this.debugStats.totalBinaryMessages}, size: ${dataSize} bytes`);
                    console.log('🔧 WebSocketService: Binary handlers to notify:', this.binaryHandlers.size);
                }
            } else {
                this.debugStats.totalTextMessages++;
                console.log(`📥 WebSocketService: Text message #${this.debugStats.totalTextMessages}: ${event.data.substring(0, 100)}...`);
            }

            this.handleMessage(event.data);
        };

        console.log('✅ WebSocketService: Event handlers setup complete');
    }

    private handleMessage(data: string | ArrayBuffer): void {

        if (data instanceof ArrayBuffer) {
            console.log(`🔄 WebSocketService: Routing binary data to ${this.binaryHandlers.size} handlers`);
            // Binary data - route to handlers
            let handlerIndex = 0;
            this.binaryHandlers.forEach((handler) => {
                handlerIndex++;
                try {
                    console.log(`🔄 WebSocketService: Calling binary handler ${handlerIndex}/${this.binaryHandlers.size}`);
                    handler(data);
                } catch (error) {
                    console.error(`❌ WebSocketService: Binary handler error:`, error);
                }
            });
        } else {
            // Handle ping/pong
            if (data === 'ping') {
                console.log('🏓 WebSocketService: Received ping, sending pong');
                this.send('pong');
                return;
            }
            if (data === 'pong') {
                console.log('🏓 WebSocketService: Received pong response');
                return;
            }

            // Try to parse JSON messages
            try {
                const message = JSON.parse(data) as WebSocketMessage;
                console.log('📨 WebSocketService: Parsed JSON message:', message.message_type || 'unknown type');

                // Process internal handlers first
                this.processInternalMessage(message);

                // Then custom handlers
                console.log(`🔄 WebSocketService: Routing to ${this.messageHandlers.size} custom handlers`);
                this.messageHandlers.forEach(handler => handler(message));
            } catch (error) {
                console.warn('⚠️ WebSocketService: Received non-JSON string message or parse error:', error);
            }
        }
    }

    private processInternalMessage(message: WebSocketMessage): void {
        console.log('🔧 WebSocketService: Processing internal message:', message.message_type);

        switch (message.message_type) {
            case 'framerate_update':
                this.handleFramerateUpdate(message as FramerateUpdateMessage);
                break;
            case 'log_record':
                this.handleLogRecord(message as LogRecordMessage);
                break;
            default:
                console.warn(`⚠️ WebSocketService: Unhandled message type: ${JSON.stringify(message).slice(0, 100)}...`);
                break;
        }
    }

    private handleFramerateUpdate(message: FramerateUpdateMessage): void {
        console.log('📊 WebSocketService: Framerate update received');
        if (message.backend_framerate) {
            store.dispatch(backendFramerateUpdated(message.backend_framerate));
        }
        if (message.frontend_framerate) {
            store.dispatch(frontendFramerateUpdated(message.frontend_framerate));
        }
    }

    private handleLogRecord(message: LogRecordMessage): void {
        console.log('📝 WebSocketService: Log record received:', message.levelname);
        store.dispatch(logAdded(message as LogRecord));
    }

    private attemptReconnect(): void {
        if (this.intentionalDisconnect || !this.config.reconnect || !this.url) {
            console.log('🚫 WebSocketService: Reconnect skipped (intentional:', this.intentionalDisconnect,
                ', reconnect enabled:', this.config.reconnect, ', url:', !!this.url, ')');
            return;
        }

        const state = store.getState();
        const isServerAlive = selectIsServerAlive(state);

        if (!isServerAlive) {
            console.log('💤 WebSocketService: Server not connected, skipping reconnect');
            return;
        }

        if (this.reconnectAttempts >= this.config.maxReconnectAttempts) {
            console.error('❌ WebSocketService: Max reconnection attempts reached');
            store.dispatch(websocketError('Max reconnection attempts reached'));
            return;
        }

        this.reconnectAttempts++;
        store.dispatch(websocketReconnecting(this.reconnectAttempts));

        const delay = Math.min(
            this.config.reconnectInterval * Math.pow(2, this.reconnectAttempts - 1),
            10000
        );

        console.log(`🔄 WebSocketService: Reconnect attempt ${this.reconnectAttempts}/${this.config.maxReconnectAttempts} in ${delay}ms`);

        this.reconnectTimer = setTimeout(() => {
            if (this.url && !this.intentionalDisconnect) {
                this.connect(this.url);
            }
        }, delay);
    }

    private setupAutoConnect(): void {
        if (!this.config.autoConnect) {
            console.log('🚫 WebSocketService: Auto-connect disabled');
            return;
        }

        console.log('🔧 WebSocketService: Setting up auto-connect');

        // Clean up existing subscription
        this.teardownAutoConnect();

        let lastServerStatus: boolean | null = null;

        // Subscribe to store changes
        this.unsubscribe = store.subscribe(() => {
            const state = store.getState();
            const isServerAlive = selectIsServerAlive(state);

            // Only react to changes in server status
            if (isServerAlive !== lastServerStatus) {
                console.log('🔄 WebSocketService: Server status changed from', lastServerStatus, 'to', isServerAlive);
                lastServerStatus = isServerAlive;

                if (isServerAlive && !this.isConnected && !this.intentionalDisconnect) {
                    console.log('🚀 WebSocketService: Server became available, auto-connecting');
                    this.connect();
                } else if (!isServerAlive && this.isConnected) {
                    console.log('💤 WebSocketService: Server became unavailable, disconnecting');
                    this.intentionalDisconnect = true;
                    this.cleanup();
                    store.dispatch(websocketDisconnected());
                }
            }
        });

        // Check initial state
        const state = store.getState();
        const isServerAlive = selectIsServerAlive(state);
        lastServerStatus = isServerAlive;

        if (isServerAlive && !this.isConnected && !this.intentionalDisconnect) {
            console.log('🚀 WebSocketService: Server available on init, auto-connecting');
            this.connect();
        }
    }

    private teardownAutoConnect(): void {
        if (this.unsubscribe) {
            console.log('🔧 WebSocketService: Tearing down auto-connect');
            this.unsubscribe();
            this.unsubscribe = null;
        }
    }

    private startHealthCheck(): void {
        this.stopHealthCheck();

        console.log('💓 WebSocketService: Starting health check, interval:', this.config.healthCheckInterval);
        this.healthCheckTimer = setInterval(() => {
            if (this.isConnected) {
                console.log('💓 WebSocketService: Sending health check ping');
                this.send('ping');
            }
        }, this.config.healthCheckInterval);
    }

    private stopHealthCheck(): void {
        if (this.healthCheckTimer) {
            console.log('💔 WebSocketService: Stopping health check');
            clearInterval(this.healthCheckTimer);
            this.healthCheckTimer = null;
        }
    }

    // Debug helper to get current stats
    getDebugStats() {
        return {
            ...this.debugStats,
            isConnected: this.isConnected,
            binaryHandlers: this.binaryHandlers.size,
            messageHandlers: this.messageHandlers.size,
            reconnectAttempts: this.reconnectAttempts,
            wsReadyState: this.ws?.readyState,
        };
    }
}

export const websocketService = WebSocketService.getInstance();
