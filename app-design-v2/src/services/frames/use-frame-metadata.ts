// hooks/use-frame-metadata.ts
import { useState, useEffect } from 'react';
import { frameRouter, type FrameMetadata } from '@/services/frames/frame-router';

/**
 * Hook to subscribe to frame metadata for all cameras
 */
export const useFrameMetadata = () => {
    const [metadata, setMetadata] = useState<Map<string, FrameMetadata>>(
        () => frameRouter.getAllCameraMetadata()
    );

    useEffect(() => {
        const unsubscribe = frameRouter.subscribeToMetadataChanges(setMetadata);
        return unsubscribe;
    }, []);

    return {
        metadata,
        cameraIds: Array.from(metadata.keys()),
        cameraCount: metadata.size,
    };
};

/**
 * Hook to subscribe to frame metadata for a specific camera
 */
export const useCameraMetadata = (cameraId: string) => {
    const [metadata, setMetadata] = useState<FrameMetadata | undefined>(
        () => frameRouter.getCameraMetadata(cameraId)
    );

    useEffect(() => {
        return frameRouter.subscribeToMetadataChanges((allMetadata) => {
            setMetadata(allMetadata.get(cameraId));
        });
    }, [cameraId]);

    return metadata;
};

/**
 * Hook to get FPS for a specific camera
 */
export const useCameraFPS = (cameraId: string) => {
    const metadata = useCameraMetadata(cameraId);
    return metadata?.fps ?? 0;
};

/**
 * Hook to get active camera count
 */
export const useActiveCameraCount = () => {
    const [count, setCount] = useState<number>(
        () => frameRouter.getAllCameraMetadata().size
    );

    useEffect(() => {
        const unsubscribe = frameRouter.subscribeToMetadataChanges((metadata) => {
            setCount(metadata.size);
        });

        return unsubscribe;
    }, []);

    return count;
};
