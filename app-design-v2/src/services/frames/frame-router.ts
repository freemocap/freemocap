// ============================================
// FRAME ROUTER (frame-router.ts) - WITH DEBUG LOGGING
// ============================================

import {BinaryFrameParser, type ParsedFrame, type ParsedPayload} from "@/services/frames/binary-frame-processor";
import {websocketService} from "@/services";

export interface FrameMetadata {
    cameraId: string;
    cameraIndex: number;
    frameNumber: number;
    timestamp: number;
    width: number;
    height: number;
    fps?: number;
}

export interface FrameAcknowledgment {
    frameNumber: number;
    displaySizes: Record<string, { width: number; height: number }>;
}

export type FrameHandler = (
    bitmap: ImageBitmap,
    metadata: FrameMetadata
) => void;

export type MetadataChangeHandler = (metadata: Map<string, FrameMetadata>) => void;

interface FrameCounter {
    count: number;
    startTime: number;
    fps: number;
}

interface FrameRouterOptions {
    enablePerformanceWarnings?: boolean;
    maxProcessingTimeMs?: number;
    staleTimeoutMs?: number;
    fpsUpdateIntervalMs?: number;
}

class FrameRouter {
    private static instance: FrameRouter;

    // Core components
    private parser: BinaryFrameParser;
    private handlers = new Map<string, Set<FrameHandler>>();

    // Metadata management
    private frameMetadata = new Map<string, FrameMetadata>();
    private metadataChangeHandlers = new Set<MetadataChangeHandler>();

    // Performance tracking
    private frameCounters = new Map<string, FrameCounter>();
    private fpsUpdateInterval: number | null = null;

    // Configuration
    private options: Required<FrameRouterOptions> = {
        enablePerformanceWarnings: true,
        maxProcessingTimeMs: 16.67, // 60fps frame time
        staleTimeoutMs: 5000,
        fpsUpdateIntervalMs: 1000,
    };

    // Statistics
    private stats = {
        totalFramesProcessed: 0,
        totalFramesDropped: 0,
        lastProcessingTime: 0,
        totalBinaryMessagesReceived: 0,
        lastBinaryMessageTime: 0,
        lastFrameNumber: -1,
    };

    private constructor(options?: FrameRouterOptions) {
        console.log('🎬 FrameRouter: Constructor called');
        if (options) {
            this.options = {...this.options, ...options};
        }

        this.parser = new BinaryFrameParser({
            parseWarningsEnabled: this.options.enablePerformanceWarnings,
            maxParseTimeMs: 5,
        });
    }

    static getInstance(options?: FrameRouterOptions): FrameRouter {
        if (!FrameRouter.instance) {
            console.log('🎬 FrameRouter: Creating new instance');
            FrameRouter.instance = new FrameRouter(options);
        }
        return FrameRouter.instance;
    }

    // ============================================
    // LIFECYCLE METHODS
    // ============================================

    initialize(): void {
        console.log('🎬 FrameRouter: Initializing...');

        // Register binary handler with WebSocket manager
        websocketService.addBinaryHandler((data: ArrayBuffer) => {
            console.log(`🎬 FrameRouter: Binary handler called, data size: ${data.byteLength} bytes`);
            this.stats.totalBinaryMessagesReceived++;
            this.stats.lastBinaryMessageTime = Date.now();

            // Log every 10th message to avoid spam
            if (this.stats.totalBinaryMessagesReceived % 10 === 1) {
                console.log(`📊 FrameRouter Stats: ${this.stats.totalBinaryMessagesReceived} binary messages received`);
                console.log(`📊 FrameRouter: Last frame number: ${this.stats.lastFrameNumber}`);
                console.log(`📊 FrameRouter: Active cameras: ${this.frameMetadata.size}`);
                console.log(`📊 FrameRouter: Subscribed handlers: ${this.handlers.size}`);
            }

            this.processBinaryFrame(data).then(
                () => {
                    if (this.stats.totalBinaryMessagesReceived % 10 === 1) {
                        console.log(`✅ FrameRouter: Successfully processed frame`);
                    }
                }
            ).catch(
                (error) => {
                    console.error('❌ FrameRouter: Error in processBinaryFrame:', error);
                }
            )
        });

        console.log('🎬 FrameRouter: Binary handler registered with WebSocket service');

        // Start FPS update timer
        this.startFPSUpdates();

        console.log('✅ FrameRouter: Initialization complete with options:', this.options);
    }

    destroy(): void {
        console.log('💥 FrameRouter: Destroying...');
        this.stopFPSUpdates();
        this.handlers.clear();
        this.frameMetadata.clear();
        this.metadataChangeHandlers.clear();
        this.frameCounters.clear();

        console.log('📊 FrameRouter: Final stats:', this.getStats());
    }

    // ============================================
    // PUBLIC API - SUBSCRIPTIONS
    // ============================================

    subscribe(cameraId: string, handler: FrameHandler): () => void {
        console.log(`➕ FrameRouter: Subscribing to camera ${cameraId}`);

        if (!this.handlers.has(cameraId)) {
            this.handlers.set(cameraId, new Set());
        }
        this.handlers.get(cameraId)!.add(handler);

        console.log(`✅ FrameRouter: Subscribed to ${cameraId}, total handlers: ${this.handlers.get(cameraId)!.size}`);

        return () => {
            const handlers = this.handlers.get(cameraId);
            if (handlers) {
                handlers.delete(handler);
                console.log(`➖ FrameRouter: Unsubscribed from ${cameraId}, remaining handlers: ${handlers.size}`);
                if (handlers.size === 0) {
                    this.handlers.delete(cameraId);
                    console.log(`🗑️ FrameRouter: Removed all handlers for ${cameraId}`);
                }
            }
        };
    }

    subscribeToMetadataChanges(handler: MetadataChangeHandler): () => void {
        console.log('➕ FrameRouter: Adding metadata change handler');
        this.metadataChangeHandlers.add(handler);

        // Immediately call with current metadata
        handler(new Map(this.frameMetadata));
        console.log(`✅ FrameRouter: Metadata handler added, total: ${this.metadataChangeHandlers.size}`);

        return () => {
            this.metadataChangeHandlers.delete(handler);
            console.log(`➖ FrameRouter: Metadata handler removed, remaining: ${this.metadataChangeHandlers.size}`);
        };
    }

    // ============================================
    // PUBLIC API - METADATA ACCESS
    // ============================================

    getCameraMetadata(cameraId: string): FrameMetadata | undefined {
        const metadata = this.frameMetadata.get(cameraId);
        console.log(`🔍 FrameRouter: Getting metadata for ${cameraId}:`, metadata ? 'found' : 'not found');
        return metadata;
    }

    getAllCameraMetadata(): Map<string, FrameMetadata> {
        console.log(`🔍 FrameRouter: Getting all metadata, ${this.frameMetadata.size} cameras`);
        return new Map(this.frameMetadata);
    }

    getActiveCameraIds(): string[] {
        const ids = Array.from(this.frameMetadata.keys());
        console.log(`🔍 FrameRouter: Active camera IDs:`, ids);
        return ids;
    }

    getCameraFPS(cameraId: string): number | null {
        const counter = this.frameCounters.get(cameraId);
        const fps = counter?.fps ?? null;
        console.log(`📊 FrameRouter: FPS for ${cameraId}: ${fps}`);
        return fps;
    }

    getStats() {
        return {
            ...this.stats,
            activeCameras: this.frameMetadata.size,
            subscribedCameras: this.handlers.size,
        };
    }

    // ============================================
    // PUBLIC API - MANAGEMENT
    // ============================================

    removeCamera(cameraId: string): void {
        console.log(`🗑️ FrameRouter: Removing camera ${cameraId}`);
        this.frameMetadata.delete(cameraId);
        this.frameCounters.delete(cameraId);
        this.handlers.delete(cameraId);
        this.notifyMetadataChange();
    }

    removeStaleCamera(cameraId: string): void {
        console.log(`⏰ FrameRouter: Removing stale camera ${cameraId}`);
        this.frameMetadata.delete(cameraId);
        this.frameCounters.delete(cameraId);
        this.notifyMetadataChange();
    }

    checkForStaleCameras(): string[] {
        const now = Date.now();
        const staleCameras: string[] = [];

        for (const [cameraId, metadata] of this.frameMetadata.entries()) {
            if (now - metadata.timestamp > this.options.staleTimeoutMs) {
                staleCameras.push(cameraId);
                this.removeStaleCamera(cameraId);
            }
        }

        if (staleCameras.length > 0) {
            console.warn(`⏰ FrameRouter: Removed ${staleCameras.length} stale cameras:`, staleCameras);
        }

        return staleCameras;
    }

    updateOptions(options: Partial<FrameRouterOptions>): void {
        console.log('🔧 FrameRouter: Updating options:', options);
        this.options = {...this.options, ...options};

        if (options.enablePerformanceWarnings !== undefined) {
            this.parser = new BinaryFrameParser({
                parseWarningsEnabled: options.enablePerformanceWarnings,
            });
        }

        if (options.fpsUpdateIntervalMs !== undefined) {
            this.stopFPSUpdates();
            this.startFPSUpdates();
        }
    }

    // ============================================
    // PRIVATE METHODS - FRAME PROCESSING
    // ============================================

    private async processBinaryFrame(data: ArrayBuffer): Promise<void> {
        const processingStart = performance.now();
        console.log(`🔄 FrameRouter: Processing binary frame, size: ${data.byteLength} bytes`);

        try {
            // Parse the binary data
            console.log('🔍 FrameRouter: Parsing binary data...');
            const payload = this.parser.parseFrameData(data);

            if (!payload) {
                console.error('❌ FrameRouter: Parser returned null payload');
                this.stats.totalFramesDropped++;
                return;
            }

            console.log(`✅ FrameRouter: Parsed payload - Frame #${payload.frameNumber}, ${payload.frames.length} cameras`);
            this.stats.lastFrameNumber = payload.frameNumber;

            // Process the parsed payload
            await this.processPayload(payload);

            // Send acknowledgment
            console.log(`📤 FrameRouter: Sending frame acknowledgment for frame ${payload.frameNumber}`);
            this.sendFrameAcknowledgment(payload);

        } catch (error) {
            console.error('❌ FrameRouter: Frame processing error:', error);
            if (error instanceof Error) {
                console.error('Stack trace:', error.stack);
            }
            this.stats.totalFramesDropped++;
        } finally {
            // Track processing time
            const processingTime = performance.now() - processingStart;
            this.stats.lastProcessingTime = processingTime;

            if (this.options.enablePerformanceWarnings &&
                processingTime > this.options.maxProcessingTimeMs) {
                console.warn(
                    `⚠️ FrameRouter: Slow processing! Took ${processingTime.toFixed(2)}ms ` +
                    `(threshold: ${this.options.maxProcessingTimeMs}ms)`
                );
            } else if (this.stats.totalBinaryMessagesReceived % 10 === 1) {
                console.log(`⏱️ FrameRouter: Processing time: ${processingTime.toFixed(2)}ms`);
            }
        }
    }

    private async processPayload(payload: ParsedPayload): Promise<void> {
        console.log(`🔄 FrameRouter: Processing payload with ${payload.frames.length} frames`);

        let metadataChanged = false;
        const bitmapPromises: Promise<void>[] = [];

        for (const frame of payload.frames) {
            console.log(`📷 FrameRouter: Processing frame for camera ${frame.cameraId} (${frame.width}x${frame.height})`);

            // Update metadata
            if (this.updateFrameMetadata(frame)) {
                metadataChanged = true;
                console.log(`📝 FrameRouter: Metadata changed for ${frame.cameraId}`);
            }

            // Update frame counter
            this.incrementFrameCounter(frame.cameraId);
            this.stats.totalFramesProcessed++;

            // Skip if no subscribers
            const handlers = this.handlers.get(frame.cameraId);
            if (!handlers || handlers.size === 0) {
                console.log(`⏭️ FrameRouter: No handlers for ${frame.cameraId}, skipping bitmap creation`);
                continue;
            }

            console.log(`🎯 FrameRouter: ${handlers.size} handlers for ${frame.cameraId}, creating bitmap`);

            // Create bitmap and notify handlers
            const promise = this.processFrame(frame, handlers);
            bitmapPromises.push(promise);
        }

        // Notify metadata changes if needed
        if (metadataChanged) {
            console.log('📢 FrameRouter: Notifying metadata changes');
            this.notifyMetadataChange();
        }

        // Wait for all bitmaps to be processed
        console.log(`⏳ FrameRouter: Waiting for ${bitmapPromises.length} bitmap operations`);
        await Promise.all(bitmapPromises);
        console.log(`✅ FrameRouter: All bitmaps processed for frame ${payload.frameNumber}`);
    }

    private async processFrame(
        frame: ParsedFrame,
        handlers: Set<FrameHandler>
    ): Promise<void> {
        console.log(`🖼️ FrameRouter: Creating bitmap for ${frame.cameraId}, JPEG size: ${frame.jpegData.length} bytes`);

        try {
            // Create blob and bitmap
            const blob = new Blob([frame.jpegData], {type: 'image/jpeg'});
            console.log(`📦 FrameRouter: Created blob for ${frame.cameraId}, size: ${blob.size}`);

            const bitmap = await createImageBitmap(blob, {
                premultiplyAlpha: 'none',
                colorSpaceConversion: 'none',
            });

            console.log(`✅ FrameRouter: Bitmap created for ${frame.cameraId}: ${bitmap.width}x${bitmap.height}`);

            // Get current metadata with latest FPS
            const metadata = this.frameMetadata.get(frame.cameraId);
            if (!metadata) {
                console.error(`❌ FrameRouter: No metadata for ${frame.cameraId}, closing bitmap`);
                bitmap.close();
                return;
            }

            // Notify all handlers
            console.log(`📢 FrameRouter: Notifying ${handlers.size} handlers for ${frame.cameraId}`);
            handlers.forEach((handler) => {
                try {
                    handler(bitmap, {...metadata});
                } catch (error) {
                    console.error(`❌ FrameRouter: Handler error for ${frame.cameraId}:`, error);
                }
            });

            // Schedule bitmap cleanup
            requestAnimationFrame(() => {
                bitmap.close();
                console.log(`🗑️ FrameRouter: Bitmap closed for ${frame.cameraId}`);
            });

        } catch (error) {
            console.error(`❌ FrameRouter: Failed to create bitmap for ${frame.cameraId}:`, error);
            this.stats.totalFramesDropped++;
        }
    }

    // ============================================
    // PRIVATE METHODS - METADATA MANAGEMENT
    // ============================================

    private updateFrameMetadata(frame: ParsedFrame): boolean {
        const existing = this.frameMetadata.get(frame.cameraId);

        if (!existing ||
            existing.width !== frame.width ||
            existing.height !== frame.height ||
            existing.cameraIndex !== frame.cameraIndex) {

            console.log(`📝 FrameRouter: Creating/updating metadata for ${frame.cameraId}`);
            this.frameMetadata.set(frame.cameraId, {
                cameraId: frame.cameraId,
                cameraIndex: frame.cameraIndex,
                frameNumber: frame.frameNumber,
                timestamp: Date.now(),
                width: frame.width,
                height: frame.height,
                fps: 0,
            });
            return true;
        }

        // Update existing metadata
        existing.frameNumber = frame.frameNumber;
        existing.timestamp = Date.now();
        return false;
    }

    private notifyMetadataChange(): void {
        console.log(`📢 FrameRouter: Notifying ${this.metadataChangeHandlers.size} metadata change handlers`);
        const metadataCopy = new Map(this.frameMetadata);
        this.metadataChangeHandlers.forEach(handler => {
            try {
                handler(metadataCopy);
            } catch (error) {
                console.error('❌ FrameRouter: Metadata change handler error:', error);
            }
        });
    }

    // ============================================
    // PRIVATE METHODS - PERFORMANCE TRACKING
    // ============================================

    private startFPSUpdates(): void {
        this.stopFPSUpdates();

        console.log(`⏱️ FrameRouter: Starting FPS updates, interval: ${this.options.fpsUpdateIntervalMs}ms`);
        this.fpsUpdateInterval = window.setInterval(() => {
            this.updateAllFPS();
        }, this.options.fpsUpdateIntervalMs);
    }

    private stopFPSUpdates(): void {
        if (this.fpsUpdateInterval !== null) {
            console.log('⏹️ FrameRouter: Stopping FPS updates');
            clearInterval(this.fpsUpdateInterval);
            this.fpsUpdateInterval = null;
        }
    }

    private updateAllFPS(): void {
        const now = Date.now();
        let hasChanges = false;

        for (const [cameraId, counter] of this.frameCounters.entries()) {
            const elapsed = now - counter.startTime;
            if (elapsed >= this.options.fpsUpdateIntervalMs) {
                const newFPS = Math.round((counter.count / elapsed) * 1000);
                counter.fps = newFPS;
                counter.count = 0;
                counter.startTime = now;

                const metadata = this.frameMetadata.get(cameraId);
                if (metadata && metadata.fps !== newFPS) {
                    metadata.fps = newFPS;
                    hasChanges = true;
                }
            }
        }

        if (hasChanges) {
            this.notifyMetadataChange();
        }
    }

    private incrementFrameCounter(cameraId: string): void {
        const now = Date.now();
        let counter = this.frameCounters.get(cameraId);

        if (!counter) {
            console.log(`📊 FrameRouter: Creating frame counter for ${cameraId}`);
            counter = {count: 1, startTime: now, fps: 0};
            this.frameCounters.set(cameraId, counter);
        } else {
            counter.count++;
        }
    }

    // ============================================
    // PRIVATE METHODS - NETWORK
    // ============================================

    private sendFrameAcknowledgment(payload: ParsedPayload): void {
        const ack: FrameAcknowledgment = {
            frameNumber: payload.frameNumber,
            displaySizes: payload.frames.reduce((acc: { [x: string]: { width: number; height: number; }; }, frame: {
                cameraId: string | number;
                width: number;
                height: number;
            }) => {
                acc[frame.cameraId] = {
                    width: frame.width,
                    height: frame.height
                };
                return acc;
            }, {} as Record<string, { width: number; height: number }>)
        };

        console.log(`📤 FrameRouter: Sending ACK for frame ${ack.frameNumber} with ${Object.keys(ack.displaySizes).length} display sizes`);

        websocketService.send(JSON.stringify({
            type: 'frame_ack',
            frame_number: ack.frameNumber,
            display_sizes: ack.displaySizes,
        }));
    }
}

export const frameRouter = FrameRouter.getInstance();
