// image-overlay/index.ts - Export all overlay components
export * from './image-overlay-system';
export * from './charuco-types';
export * from './charuco-overlay-renderer';
export * from './overlay-types';
export * from './overlay-renderer-factory';

// Explicitly re-export to avoid duplicate symbol conflicts
// (mediapipe-overlay-renderer re-declares types from mediapipe-types)
export {
    MediapipePointSchema,
    MediapipeMetadataSchema,
    MediapipeOverlaySchema,
    MediapipeOverlayDataMessageSchema,
    type MediapipePoint,
    type MediapipeMetadata,
    type MediapipeObservation,
    type MediapipeOverlayDataMessage
} from './mediapipe-types';
export { MediapipeOverlayRenderer } from './mediapipe-overlay-renderer';