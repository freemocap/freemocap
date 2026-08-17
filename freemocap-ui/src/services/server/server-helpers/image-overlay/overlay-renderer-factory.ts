// overlay-renderer-factory.ts
//
// The OverlayManager: composites each camera frame's overlays onto the decoded
// bitmap. (The old OverlayRendererFactory + tracker-schema/model-info wiring was
// removed with the schema→self-describing cutover; the skeleton overlay is now
// self-describing, and the charuco overlay is the remaining conversion target.)

import {CharucoOverlayRenderer} from './charuco-overlay-renderer';
import {SkeletonOverlayRenderer} from './skeleton-overlay-renderer';
import type {CharucoObservation} from './charuco-types';
import type {SkeletonObservation} from './skeleton-types';

/**
 * Manager for compositing the per-camera overlays onto a frame, chained
 * sequentially: source → charuco → skeleton. Each renderer draws on top of the
 * previous result rather than clearing and redrawing from scratch.
 */
export class OverlayManager {
    private charucoRenderer: CharucoOverlayRenderer = new CharucoOverlayRenderer();
    private skeletonRenderer: SkeletonOverlayRenderer = new SkeletonOverlayRenderer();

    public async processFrame(
        sourceBitmap: ImageBitmap,
        charucoObservation: CharucoObservation | null,
        skeletonObservation: SkeletonObservation | null,
    ): Promise<ImageBitmap> {
        let currentBitmap = sourceBitmap;

        if (charucoObservation) {
            currentBitmap = await this.charucoRenderer.compositeFrame(currentBitmap, charucoObservation);
        }

        if (skeletonObservation) {
            currentBitmap = await this.skeletonRenderer.compositeFrame(currentBitmap, skeletonObservation);
        }

        return currentBitmap;
    }

    public clearAll(): void {
        this.charucoRenderer.destroy();
        this.skeletonRenderer.destroy();
        this.charucoRenderer = new CharucoOverlayRenderer();
        this.skeletonRenderer = new SkeletonOverlayRenderer();
    }
}
