import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import {CameraImageData} from "@/context/websocket-context/useWebsocketBinaryMessageProcessor";

interface ImageMeshProps {
    cameraImageData: CameraImageData;
    position: [number, number, number];
}

export const ImageMesh: React.FC<ImageMeshProps> = ({ cameraImageData, position }) => {
    const meshRef = useRef<THREE.Mesh>(null);
    const textureRef = useRef<THREE.Texture | null>(null);
    const [aspectRatio, setAspectRatio] = useState(2);

    // Create and update texture from ImageBitmap
    useEffect(() => {
        const { imageBitmap } = cameraImageData;
        if (!imageBitmap || !meshRef.current) return;

        let isMounted = true;

        const updateTexture = async () => {
            if (!imageBitmap) return;
            try {

                if (!isMounted) {
                    imageBitmap.close();
                    return;
                }

                // Update aspect ratio
                const newAspectRatio = imageBitmap.width / imageBitmap.height;
                setAspectRatio(newAspectRatio);

                // Create texture from ImageBitmap
                if (textureRef.current) {
                    textureRef.current.dispose(); // Clean up previous texture
                }

                const newTexture = new THREE.CanvasTexture(imageBitmap);
                textureRef.current = newTexture;

                // Update material
                if (meshRef.current?.material instanceof THREE.MeshBasicMaterial) {
                    meshRef.current.material.map = newTexture;
                    meshRef.current.material.needsUpdate = true;
                }
            } catch (error) {
                console.error('Error processing image:', error);
            }
        };

        updateTexture();

        return () => {
            isMounted = false;
            // Clean up texture on unmount
            if (textureRef.current) {
                textureRef.current.dispose();
                textureRef.current = null;
            }
        };
    }, [cameraImageData]);

    // Calculate dimensions for the plane geometry
    const width = 2;
    const height = width / aspectRatio;

    return (
        <mesh ref={meshRef} position={position}>
            <planeGeometry args={[width, height]} />
            <meshBasicMaterial transparent={true} />
        </mesh>
    );
};
