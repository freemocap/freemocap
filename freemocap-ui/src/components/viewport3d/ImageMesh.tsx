import {useEffect, useMemo, useRef} from 'react';
import {useFrame} from '@react-three/fiber';
import * as THREE from 'three';
import {useServer} from '@/services';

interface ImageMeshProps {
    cameraId: string;
    position: [number, number, number];
}

export function ImageMesh({ cameraId, position }: ImageMeshProps) {
    const { subscribeToFrames } = useServer();

    const currentBitmapRef = useRef<ImageBitmap | null>(null);
    const textureRef = useRef<THREE.Texture | null>(null);
    const hasNewFrameRef = useRef<boolean>(false);

    // FIX 1: Change from CanvasTexture to Texture
    const texture = useMemo(() => {
        const tex = new THREE.Texture(); // ← Changed from CanvasTexture
        tex.minFilter = THREE.LinearFilter;
        tex.magFilter = THREE.LinearFilter;
        tex.format = THREE.RGBAFormat;
        tex.generateMipmaps = false;
        textureRef.current = tex;
        return tex;
    }, []);

    const material = useMemo(() => {
        return new THREE.MeshBasicMaterial({
            map: texture,
            side: THREE.DoubleSide,
        });
    }, [texture]);

    // FIX 2: Subscribe with cameraId parameter
    useEffect(() => {
        const unsubscribe = subscribeToFrames(cameraId, (bitmap) => {
            // Close previous bitmap to free memory
            if (currentBitmapRef.current) {
                currentBitmapRef.current.close();
            }
            currentBitmapRef.current = bitmap;
            hasNewFrameRef.current = true;
        });

        return () => {
            unsubscribe();
            if (currentBitmapRef.current) {
                currentBitmapRef.current.close();
                currentBitmapRef.current = null;
            }
        };
    }, [cameraId, subscribeToFrames]);

    // Update texture in render loop
    useFrame(() => {
        if (hasNewFrameRef.current && currentBitmapRef.current && textureRef.current) {
            textureRef.current.image = currentBitmapRef.current;
            textureRef.current.needsUpdate = true;
            hasNewFrameRef.current = false;
        }
    });

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
