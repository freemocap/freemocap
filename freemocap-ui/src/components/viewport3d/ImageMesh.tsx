import { useEffect, useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { useServer } from '@/services';

interface ImageMeshProps {
    cameraId: string;
    position: [number, number, number];
}

export function ImageMesh({ cameraId, position }: ImageMeshProps) {
    const { subscribeToFrames } = useServer();

    // Store the current bitmap (don't null it out - keep it alive for texture)
    const currentBitmapRef = useRef<ImageBitmap | null>(null);
    const textureRef = useRef<THREE.Texture | null>(null);
    const hasNewFrameRef = useRef<boolean>(false);

    // Create texture once - use regular Texture, not CanvasTexture
    const texture = useMemo(() => {
        const tex = new THREE.CanvasTexture();
        tex.minFilter = THREE.LinearFilter;
        tex.magFilter = THREE.LinearFilter;
        tex.format = THREE.RGBAFormat;
        tex.generateMipmaps = false;
        textureRef.current = tex;
        return tex;
    }, []);

    // Create material once
    const material = useMemo(() => {
        return new THREE.MeshBasicMaterial({
            map: texture,
            side: THREE.DoubleSide,
        });
    }, [texture]);

    // Subscribe to frame updates
    useEffect(() => {
        const unsubscribe = subscribeToFrames((camId, bitmap) => {
            if (camId === cameraId) {
                // Close previous bitmap to free memory
                if (currentBitmapRef.current) {
                    currentBitmapRef.current.close();
                }
                currentBitmapRef.current = bitmap;
                hasNewFrameRef.current = true;
            } else {
                // CRITICAL: Close bitmaps that aren't for this camera to prevent memory leak
                bitmap.close();
            }
        });

        return () => {
            unsubscribe();
            if (currentBitmapRef.current) {
                currentBitmapRef.current.close();
                currentBitmapRef.current = null;
            }
        };
    }, [cameraId, subscribeToFrames]);

    // Update texture in render loop (efficient, only when new frame arrives)
    useFrame(() => {
        if (hasNewFrameRef.current && currentBitmapRef.current && textureRef.current) {
            // Update texture source to ImageBitmap
            textureRef.current.image = currentBitmapRef.current;
            textureRef.current.needsUpdate = true;

            // Clear the flag, but DON'T null out the bitmap - keep it for rendering
            hasNewFrameRef.current = false;
        }
    });

    // Calculate mesh size based on image aspect ratio
    // Will dynamically resize when first frame arrives
    const meshGeometry = useMemo(() => {
        const height = 2.0;
        const width = height * (16 / 9);
        return new THREE.PlaneGeometry(width, height);
    }, []);

    return (
        <mesh
            position={position}
            geometry={meshGeometry}
            material={material}
        />
    );
}