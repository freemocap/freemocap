// overlay-renderer-factory.ts
import { CharucoOverlayRenderer } from './charuco-overlay-renderer';
import { MediapipeOverlayRenderer, MediapipeObservation } from './mediapipe-overlay-renderer';
import {BaseOverlayRenderer, ModelInfo} from "@/services/server/server-helpers/image-overlay/image-overlay-system";
import {CharucoObservation} from "@/services/server/server-helpers/image-overlay/charuco-types";

export type ObservationType = 'charuco_overlay' | 'mediapipe_overlay' | 'rtmpose_overlay';


/**
 * Factory for creating appropriate overlay renderers based on observation type
 */
export class OverlayRendererFactory {
    private static rendererCache: Map<ObservationType, BaseOverlayRenderer> = new Map();
    private static modelInfoCache: Map<string, ModelInfo> = new Map();

    /**
     * Get or create a renderer for the specified observation type
     */
    public static getRenderer(type: ObservationType): BaseOverlayRenderer {
        // Check cache first
        let renderer = this.rendererCache.get(type);
        if (renderer) {
            return renderer;
        }

        // Create new renderer based on type
        switch (type) {
            case 'charuco_overlay':
                renderer = new CharucoOverlayRenderer();
                break;
            case 'mediapipe_overlay':
                renderer = new MediapipeOverlayRenderer();
                break;
            case 'rtmpose_overlay':
                // Future: implement RTMPoseOverlayRenderer
                throw new Error('RTMPose overlay not yet implemented');
            default:
                throw new Error(`Unknown observation type: ${type}`);
        }

        this.rendererCache.set(type, renderer);
        return renderer;
    }

    /**
     * Set model info for a specific tracker type
     */
    public static setModelInfo(trackerName: string, modelInfo: ModelInfo): void {
        this.modelInfoCache.set(trackerName, modelInfo);

        // Update all renderers that might use this model info
        for (const [type, renderer] of this.rendererCache) {
            if (this.shouldUseModelInfo(type, trackerName)) {
                renderer.setModelInfo(modelInfo);
            }
        }
    }

    /**
     * Clear all cached renderers
     */
    public static clearCache(): void {
        for (const renderer of this.rendererCache.values()) {
            renderer.destroy();
        }
        this.rendererCache.clear();
        this.modelInfoCache.clear();
    }

    /**
     * Determine if a renderer type should use a specific model info
     */
    private static shouldUseModelInfo(
        rendererType: ObservationType,
        trackerName: string
    ): boolean {
        const mapping: Record<ObservationType, string[]> = {
            'charuco_overlay': ['CharucoTracker'],
            'mediapipe_overlay': ['MediapipeHolisticTracker', 'MediapipeTracker'],
            'rtmpose_overlay': ['RTMPoseTracker'],
        };

        return mapping[rendererType]?.includes(trackerName) || false;
    }
}

/**
 * Manager for handling overlay rendering across multiple cameras
 */
export class OverlayManager {
    private renderers: Map<string, BaseOverlayRenderer> = new Map();
    private observationTypeMap: Map<string, ObservationType> = new Map();

    /**
     * Process a frame with overlay
     */
    public async processFrame(
        cameraId: string,
        sourceBitmap: ImageBitmap,
        observation: CharucoObservation | MediapipeObservation | null
    ): Promise<ImageBitmap> {
        // Determine observation type
        const observationType = observation?.message_type as ObservationType;

        if (!observationType && !observation) {
            // No observation, just return the source bitmap
            return sourceBitmap;
        }

        // Get or create renderer for this camera
        let renderer = this.renderers.get(cameraId);
        const previousType = this.observationTypeMap.get(cameraId);

        // Check if we need a different renderer type
        if (!renderer || previousType !== observationType) {
            renderer = OverlayRendererFactory.getRenderer(observationType);
            this.renderers.set(cameraId, renderer);
            this.observationTypeMap.set(cameraId, observationType);
        }

        // Process the frame
        return renderer.compositeFrame(sourceBitmap, observation);
    }

    /**
     * Clear renderer for a specific camera
     */
    public clearCamera(cameraId: string): void {
        const renderer = this.renderers.get(cameraId);
        if (renderer) {
            renderer.destroy();
            this.renderers.delete(cameraId);
            this.observationTypeMap.delete(cameraId);
        }
    }

    /**
     * Clear all renderers
     */
    public clearAll(): void {
        for (const renderer of this.renderers.values()) {
            renderer.destroy();
        }
        this.renderers.clear();
        this.observationTypeMap.clear();
    }
}
