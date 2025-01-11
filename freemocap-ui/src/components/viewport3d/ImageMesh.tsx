import React, { useEffect, useRef } from 'react';
import { useLoader } from '@react-three/fiber';
import * as THREE from 'three';

interface ImageMeshProps {
    imageUrl: string;
    position: [number, number, number];
}

export const ImageMesh: React.FC<ImageMeshProps> = ({ imageUrl, position }) => {
    const texture = useLoader(THREE.TextureLoader, imageUrl);
    const meshRef = useRef<THREE.Mesh>(null);

    useEffect(() => {
        if (meshRef.current) {
            meshRef.current.material.map = texture;
            meshRef.current.material.needsUpdate = true;
        }
    }, [texture]);

    return (
        <mesh ref={meshRef} position={position}>
            <planeGeometry args={[2, 1]} />
            <meshBasicMaterial />
        </mesh>
    );
};
