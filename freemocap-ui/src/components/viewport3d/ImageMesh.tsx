import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { CameraImageData } from "@/context/websocket-context/useWebsocketBinaryMessageProcessor";
import { useWebSocketContext } from "@/context/websocket-context/WebSocketContext";
import {Vector3} from "three";

interface ImageMeshProps {
    cameraImageData: CameraImageData;
    position:  [number, number, number];
}

export const ImageMesh: React.FC<ImageMeshProps> = ({ cameraImageData, position }) => {
    const { cameraId, imageBitmap, imageWidth, imageHeight, frameNumber } = cameraImageData;
    const { acknowledgeFrameRendered } = useWebSocketContext();
    const meshRef = useRef<THREE.Mesh>(null);
    const textureRef = useRef<THREE.Texture | null>(null);
    const [aspectRatio, setAspectRatio] = useState(2);

    // Initialize texture once
    useEffect(() => {
        // Create texture only once and reuse it
        if (!textureRef.current) {
            const newTexture = new THREE.Texture();
            // Set Color Management
            newTexture.minFilter = THREE.LinearFilter;
            newTexture.magFilter = THREE.LinearFilter;

            // Do a buncha weird nonsense to get the image to show up correctly in the scene
            newTexture.wrapS = THREE.RepeatWrapping;
            newTexture.repeat.x = -1; // Flip texture horizontally
            newTexture.center = new THREE.Vector2(0.5, 0.5);
            newTexture.rotation = Math.PI;
            newTexture.flipY = false;
            textureRef.current = newTexture;
        }

        return () => {
            // Clean up texture on unmount
            if (textureRef.current) {
                textureRef.current.dispose();
                textureRef.current = null;
            }
        };
    }, []);

    // Update texture with new image data
    useEffect(() => {
        if (!imageBitmap || !meshRef.current || !textureRef.current) return;

        try {
            // Update aspect ratio only when dimensions change
            const newAspectRatio = imageWidth / imageHeight;
            if (aspectRatio !== newAspectRatio) {
                setAspectRatio(newAspectRatio);
            }

            // Update texture with new image data without creating a new texture
            textureRef.current.image = imageBitmap;
            textureRef.current.flipY = true;

            textureRef.current.needsUpdate = true;

            // Apply texture to material if not already applied
            if (meshRef.current.material instanceof THREE.MeshBasicMaterial) {
                if (meshRef.current.material.map !== textureRef.current) {
                    meshRef.current.material.map = textureRef.current;
                }
                meshRef.current.material.needsUpdate = true;
            }

            // Acknowledge that the frame was rendered
            acknowledgeFrameRendered(cameraId, frameNumber);
        } catch (error) {
            console.error('Error processing image:', error);
        }
    }, [cameraId, imageBitmap, imageWidth, imageHeight, frameNumber, aspectRatio, acknowledgeFrameRendered]);

    // Calculate dimensions for the plane geometry
    let meshWidth, meshHeight;
    if (imageWidth >= imageHeight) {
        const meshWidth = 2;
        const meshHeight = meshWidth / aspectRatio;
    } else {
        const meshHeight = 2;
        const meshWidth = meshHeight * aspectRatio;
    }

    return (
        <mesh ref={meshRef} position={position}>
            <planeGeometry args={[imageWidth/300, imageHeight/300]} />
            <meshBasicMaterial transparent={false} />
        </mesh>
    );
};
