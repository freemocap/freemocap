// overlay-renderer-factory.ts
import {CharucoOverlayRenderer} from './charuco-overlay-renderer';
import {MediapipeObservation, MediapipeOverlayRenderer} from './mediapipe-overlay-renderer';
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
 * Manager for handling overlay rendering across multiple cameras.
 *
 * Composites both charuco and mediapipe overlays sequentially onto each
 * frame: source → charuco → mediapipe. Each renderer draws on top of
 * the previous result rather than clearing and redrawing from scratch.
 */
export class OverlayManager {
    private charucoRenderer: CharucoOverlayRenderer = new CharucoOverlayRenderer();
    private mediapipeRenderer: MediapipeOverlayRenderer = new MediapipeOverlayRenderer();

    /**
     * Composite both overlay types onto a single frame, chained sequentially.
     * The charuco overlay is drawn first, then mediapipe on top of the result.
     */
    public async processFrame(
        cameraId: string,
        sourceBitmap: ImageBitmap,
        charucoObservation: CharucoObservation | null,
        mediapipeObservation: MediapipeObservation | null,
    ): Promise<ImageBitmap> {
        let currentBitmap = sourceBitmap;

        if (charucoObservation) {
            currentBitmap = await this.charucoRenderer.compositeFrame(
                currentBitmap,
                charucoObservation,
            );
        }

        if (mediapipeObservation) {
            currentBitmap = await this.mediapipeRenderer.compositeFrame(
                currentBitmap,
                mediapipeObservation,
            );
        }

        return currentBitmap;
    }

    /**
     * Set model info on both renderers
     */
    public setModelInfo(modelInfo: ModelInfo): void {
        this.charucoRenderer.setModelInfo(modelInfo);
        this.mediapipeRenderer.setModelInfo(modelInfo);
    }

    /**
     * Clear all renderers
     */
    public clearAll(): void {
        this.charucoRenderer.destroy();
        this.mediapipeRenderer.destroy();
        this.charucoRenderer = new CharucoOverlayRenderer();
        this.mediapipeRenderer = new MediapipeOverlayRenderer();
    }
}
